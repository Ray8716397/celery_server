# -*- encoding: utf-8 -*-
'''
@File    :   sam_process.py
@Modify Time      @Author    @Version    @Desciption
------------      -------    --------    -----------
2023/8/10 上午10:21   zzg      1.0         None
'''

import datetime
import os
from lib.common.common_util import logging
from lib.redis_pipline.operator import Operator
from modules.devices import torch_gc, device
from modules.safe import unsafe_torch_load, load
from segment_anything import SamPredictor, sam_model_registry
import copy
import gc
from collections import OrderedDict
from PIL import Image
import numpy as np
import gradio as gr
import torch
from scipy.ndimage import label
from guiju.segment_anything_util.dino import dino_model_list, dino_predict_internal, show_boxes, dino_install_issue_text
from guiju.segment_anything_util.sam import sam_model_list, sam_predict
from modules import shared, scripts
import modules.img2img
from modules.shared import cmd_opts
import random
import string
import traceback
import cv2
import io
import math


class OperatorSAM(Operator):
    num = 2
    cache = True
    cuda = True

    def __init__(self):
        Operator.__init__(self)
        """ load sam model """
        self.sam_model_cache = OrderedDict()
        self.sam_model_dir = 'extensions/sd-webui-segment-anything/models/sam'
        self.sam_model_list = [f for f in os.listdir(self.sam_model_dir) if
                               os.path.isfile(os.path.join(self.sam_model_dir, f)) and f.split('.')[-1] != 'txt']
        self.sam_model = self.init_sam_model(self.sam_model_list[0])
        print('SAM model is Initialized')

    def garbage_collect(self):
        gc.collect()
        torch_gc()

    def clear_sam_cache(self):
        self.sam_model_cache.clear()
        gc.collect()
        torch_gc()

    def init_sam_model(self, sam_model_name):
        print("Initializing SAM")
        if sam_model_name in self.sam_model_cache:
            sam = self.sam_model_cache[sam_model_name]
            return sam
        elif sam_model_name in self.sam_model_list:
            self.clear_sam_cache()
            self.sam_model_cache[sam_model_name] = self.load_sam_model(sam_model_name)
            return self.sam_model_cache[sam_model_name]
        else:
            Exception(
                f"{sam_model_name} not found, please download model to models/sam.")

    def load_sam_model(self, sam_checkpoint):
        model_type = '_'.join(sam_checkpoint.split('_')[1:-1])
        sam_checkpoint = os.path.join(self.sam_model_dir, sam_checkpoint)
        torch.load = unsafe_torch_load
        sam = sam_model_registry[model_type](checkpoint=sam_checkpoint)
        sam.to(device=device)
        sam.eval()
        torch.load = load
        return sam

    def configure_image(self, image, person_pos, target_ratio=0.5, quality=90):
        person_pos = [int(x) for x in person_pos]
        # 将PIL RGBA图像转换为BGR图像
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGBA2BGRA)

        # 获取原始图像的尺寸
        original_height, original_width = cv_image.shape[:2]

        # 计算模特图像的长宽比
        person_height = person_pos[3] - person_pos[1]
        person_width = person_pos[2] - person_pos[0]
        person_ratio = person_width / person_height

        # 计算应该添加的填充量
        if person_ratio > target_ratio:
            # 需要添加垂直box
            target_height = int(person_width / target_ratio)
            remainning_height = original_height - target_height
            if remainning_height >= 0:
                top = int((target_height - person_height) / 2)
                bottom = target_height - person_height - top
                if person_pos[1] - top < 0:
                    padded_image = cv_image[:person_pos[3] + bottom - person_pos[1] + top, person_pos[0]:person_pos[2]]

                else:
                    padded_image = cv_image[person_pos[1] - top:person_pos[3] + bottom, person_pos[0]:person_pos[2]]
            else:
                top = int((target_height - original_height) / 2)
                bottom = target_height - original_height - top
                padded_image = cv2.copyMakeBorder(cv_image, top, bottom, 0, 0, cv2.BORDER_REPLICATE)
                padded_image = padded_image[:, person_pos[0]:person_pos[2]]
        else:
            # 需要添加水平box
            target_width = int(person_height * target_ratio)
            remainning_width = original_width - target_width
            if remainning_width >= 0:
                left = int((target_width - person_width) / 2)
                right = target_width - person_width - left

                if person_pos[0] - left < 0:
                    padded_image = cv_image[person_pos[1]:person_pos[3], :person_pos[2] + right - person_pos[0] + left]

                else:
                    padded_image = cv_image[person_pos[1]:person_pos[3], person_pos[0] - left:person_pos[2] + right]
            else:
                left = int((target_width - original_width) / 2)
                right = target_width - original_width - left
                padded_image = cv2.copyMakeBorder(cv_image, 0, 0, left, right, cv2.BORDER_REPLICATE)
                padded_image = padded_image[person_pos[1]:person_pos[3], :]
        # 压缩图像质量
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, jpeg_data = cv2.imencode('.jpg', padded_image, encode_param)
        # 将压缩后的图像转换为PIL图像
        pil_image = Image.open(io.BytesIO(jpeg_data)).convert('RGBA')
        return pil_image

    def padding_rgba_image_pil_to_cv(self, original_image, pl, pr, pt, pb):
        original_width, original_height = original_image.size
        #     # 获取原图的边缘颜色
        edge_color = original_image.getpixel((0, 0))
        #     # 创建新的空白图像并粘贴原始图像
        padded_image = Image.new('RGBA', (original_width + pl + pr, original_height + pt + pb), edge_color)
        padded_image.paste(original_image, (pl, pt), mask=original_image)
        return padded_image

    def get_prompt(self, _gender, _age, _viewpoint, _model_mode=0):
        sd_positive_prompts_dict = OrderedDict({
            'gender': [
                # female
                '1girl',
                # male
                '1boy',
            ],
            'age': [
                # child
                f'(child:1.3){"" if _gender else ", <lora:shojovibe_v11:0.4> ,<lora:koreanDollLikeness:0.4>"}',
                # youth
                f'(youth:1.3){"" if _gender else ", <lora:shojovibe_v11:0.4> ,<lora:koreanDollLikeness:0.4>"}',
                # middlescent
                '(middlescent:1.3)',
            ],
            'common': [
                '(RAW photo, best quality)',
                '(realistic, photo-realistic:1.3)',
                'masterpiece',
                # f'(a naked {"man" if _gender else "woman"}:1.5)',
                f'an extremely delicate and {"handsome" if _gender else "beautiful"} {"male" if _gender else "female"}',
                'extremely detailed CG unity 8k wallpaper',
                'highres',
                'detailed fingers',
                'realistic fingers',
                # 'sleeves past wrist',
                'beautiful detailed nose',
                'beautiful detailed eyes',
                'detailed hand',
                'realistic hand',
                # 'detailed foot',
                'realistic body',
                '' if _gender else 'fluffy hair',
                '' if _viewpoint == 2 else 'posing for a photo, normal foot posture, light on face, realistic face',
                '(simple background:1.3)',
                '(white background:1.3)',
                'full body' if _model_mode == 0 else '(full body:1.8)',
            ],
            'viewpoint': [
                # 正面
                'light smile',
                # 侧面
                'light smile, a side portrait photo of a people, (looking to the side:1.5)',
                # 反面
                '(a person with their back to the camera:1.5)'
            ]
        })

        sd_positive_prompts_dict['common'] = [x for x in sd_positive_prompts_dict['common'] if x]
        sd_positive_prompts_dict['gender'] = [sd_positive_prompts_dict['gender'][_gender]]
        sd_positive_prompts_dict['age'] = [sd_positive_prompts_dict['age'][_age]]
        sd_positive_prompts_dict['viewpoint'] = [sd_positive_prompts_dict['viewpoint'][_viewpoint]]

        if _viewpoint == 2:
            sd_positive_prompt = f'(RAW photo, best quality), (realistic, photo-realistic:1.3), masterpiece, 2k wallpaper,realistic body, (simple background:1.3), (white background:1.3), (from behind:1.3){", 1boy" if _gender else ""}'

        else:
            sd_positive_prompt = ', '.join([i for x in sd_positive_prompts_dict.values() for i in x])

        sd_negative_prompt = '(extra clothes:1.5),(clothes:1.5),(NSFW:1.3),paintings, sketches, (worst quality:2), (low quality:2), (normal quality:2), clothing, pants, shorts, t-shirt, dress, sleeves, lowres, ((monochrome)), ((grayscale)), duplicate, morbid, mutilated, mutated hands, poorly drawn face,skin spots, acnes, skin blemishes, age spot, glans, extra fingers, fewer fingers, ((watermark:2)), (white letters:1), (multi nipples), bad anatomy, bad hands, text, error, missing fingers, missing arms, missing legs, extra digit, fewer digits, cropped, worst quality, jpeg artifacts, signature, watermark, username, bad feet, Multiple people, blurry, poorly drawn hands, mutation, deformed, extra limbs, extra arms, extra legs, malformed limbs, too many fingers, long neck, cross-eyed, polar lowres, bad body, bad proportions, gross proportions, wrong feet bottom render, abdominal stretch, briefs, knickers, kecks, thong, fused fingers, bad body, bad-picture-chill-75v, ng_deepnegative_v1_75t, EasyNegative, bad proportion body to legs, wrong toes, extra toes, missing toes, weird toes, 2 body, 2 pussy, 2 upper, 2 lower, 2 head, 3 hand, 3 feet, extra long leg, super long leg, mirrored image, mirrored noise, (bad_prompt_version2:0.8), aged up, old fingers, long neck, cross-eyed, polar lowres, bad body, bad proportions, gross proportions, wrong feet bottom render, abdominal stretch, briefs, knickers, kecks, thong, bad body, bad-picture-chill-75v, ng_deepnegative_v1_75t, EasyNegative, bad proportion body to legs, wrong toes, extra toes, missing toes, weird toes, 2 body, 2 pussy, 2 upper, 2 lower, 2 head, 3 hand, 3 feet, extra long leg, super long leg, mirrored image, mirrored noise, (bad_prompt_version2:0.8)'

        return sd_positive_prompt, sd_negative_prompt

    def operation(self, *args, **kwargs):
        _batch_size = kwargs['_batch_size']
        _input_image = kwargs['_input_image']
        _gender = kwargs['_gender']
        _age = kwargs['_age']
        _viewpoint_mode = kwargs['_viewpoint_mode']
        _cloth_part = kwargs['_cloth_part']
        _model_mode = kwargs['_model_mode']
        try:
            _batch_size = int(_batch_size)
            shared.state.interrupted = False
            output_height = 1024
            output_width = 512
            _sam_model_name = sam_model_list[0]
            _dino_model_name = dino_model_list[1]
            _dino_text_prompt = 'clothing . pants . shorts . t-shirt . dress'
            _box_threshold = 0.3
            if _input_image is None:
                return None, None
            else:
                _input_image.save(f'tmp/origin_{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.png',
                                  format='PNG')
                try:
                    # real people
                    if _model_mode == 0:
                        person_boxes, _ = dino_predict_internal(_input_image, _dino_model_name, "person",
                                                                _box_threshold)
                        _input_image = self.configure_image(_input_image, person_boxes[0],
                                                            target_ratio=output_width / output_height)
                        pass
                    # artificial model
                    else:
                        _input_image_width, _input_image_height = _input_image.size
                        person_boxes, _ = dino_predict_internal(_input_image, _dino_model_name, "clothing",
                                                                _box_threshold)
                        person0_box = [int(x) for x in person_boxes[0]]
                        person0_width = person0_box[2] - person0_box[0]
                        person0_height = person0_box[3] - person0_box[1]
                        constant_bottom = 30
                        constant_top = 15
                        factor_bottom = 7
                        factor_top = 4
                        left_ratio = 0.1
                        right_ratio = 0.1
                        # top_ratio = 0.32
                        top_ratio = min(0.32, math.pow(person0_width / person0_height, factor_top) * constant_top)
                        bottom_ratio = min(0.54,
                                           math.pow(person0_width / person0_height, factor_bottom) * constant_bottom)
                        print(f"bottom_ratio: {bottom_ratio}")
                        print(f"top_ratio: {top_ratio}")
                        print(f"boxes: {person_boxes}")
                        print(f"width: {person0_width}")
                        print(f"height: {person0_height}")
                        print(f"increase: {person0_height * bottom_ratio}")

                        padding_left = int(person0_width * left_ratio - int(person0_box[0])) if \
                            (int(person0_box[0]) / person0_width) < left_ratio else 0

                        padding_right = int(person0_width * right_ratio - (_input_image_width - int(person0_box[2]))) \
                            if ((_input_image_width - int(person0_box[2])) / person0_width) < right_ratio else 0

                        padding_top = int(person0_height * top_ratio - int(person0_box[1])) if \
                            (int(person0_box[1]) / person0_height) < top_ratio else 0

                        padding_bottom = int(
                            person0_height * bottom_ratio - (_input_image_height - int(person0_box[3]))) if \
                            ((_input_image_height - int(person0_box[3])) / person0_height) < bottom_ratio else 0

                        _input_image = self.padding_rgba_image_pil_to_cv(_input_image, padding_left, padding_right,
                                                                         padding_top, padding_bottom)
                        _input_image = self.configure_image(_input_image,
                                                            [0 if padding_left > 0 else person0_box[0] - int(person0_width * left_ratio),
                                                             0 if padding_top > 0 else person0_box[1] - int(person0_height * top_ratio),
                                                             padding_left + _input_image_width + padding_right if
                                                             padding_right > 0 else padding_left + person0_box[2] + int(person0_width * right_ratio),
                                                             padding_top + _input_image_height + padding_bottom
                                                             if padding_bottom > 0 else padding_top + person0_box[3] + int(person0_height * bottom_ratio)],
                                                            target_ratio=output_width / output_height)

                except Exception:
                    print(traceback.format_exc())
                    print('preprocess img error')

                if cmd_opts.debug_mode:
                    _input_image.save(f'tmp/resized_{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.png',
                                      format='PNG')

            sam_result_tmp_png_fp = []

            sam_result_gallery, sam_result = sam_predict(_dino_model_name, _dino_text_prompt,
                                                         _box_threshold,
                                                         _input_image)

            pic_name = ''.join([random.choice(string.ascii_letters) for c in range(15)])
            for idx, sam_mask_img in enumerate(sam_result_gallery):
                cache_fp = f"tmp/{idx}_{pic_name}.png"
                sam_mask_img.save(cache_fp)
                sam_result_tmp_png_fp.append({'name': cache_fp})
            task_id = f"task({''.join([random.choice(string.ascii_letters) for c in range(15)])})"
            sd_positive_prompt, sd_negative_prompt = self.get_prompt(_gender, _age, _viewpoint_mode, _model_mode)
            prompt_styles = None
            init_img = _input_image
            sketch = None
            init_img_with_mask = None
            inpaint_color_sketch = None
            inpaint_color_sketch_orig = None
            init_img_inpaint = None
            init_mask_inpaint = None
            steps = 20
            sampler_index = 18  # sampling method modules/sd_samplers_kdiffusion.py
            mask_blur = 4
            mask_alpha = 0
            inpainting_fill = 1
            restore_faces = True
            tiling = False
            n_iter = 1
            batch_size = _batch_size
            cfg_scale = 7
            image_cfg_scale = 1.5
            denoising_strength = 0.7
            seed = -1.0
            subseed = -1.0
            subseed_strength = 0
            seed_resize_from_h = 0
            seed_resize_from_w = 0
            seed_enable_extras = False
            selected_scale_tab = 0
            height = output_height
            width = output_width
            scale_by = 1
            resize_mode = 2
            inpaint_full_res = 0  # choices=["Whole picture", "Only masked"]
            inpaint_full_res_padding = 0
            inpainting_mask_invert = 1
            img2img_batch_input_dir = ''
            img2img_batch_output_dir = ''
            img2img_batch_inpaint_mask_dir = ''
            override_settings_texts = []
            # controlnet args
            cnet_idx = 1
            controlnet_args_unit1 = modules.scripts.scripts_img2img.alwayson_scripts[cnet_idx].get_default_ui_unit()
            controlnet_args_unit1.batch_images = ''
            controlnet_args_unit1.control_mode = 'Balanced' if _model_mode == 0 else 'My prompt is more important'
            controlnet_args_unit1.enabled = _model_mode == 0
            # controlnet_args_unit1.enabled = False
            controlnet_args_unit1.guidance_end = 0.8
            controlnet_args_unit1.guidance_start = 0  # ending control step
            controlnet_args_unit1.image = None
            # controlnet_args_unit1.input_mode = batch_hijack.InputMode.SIMPLE
            controlnet_args_unit1.low_vram = False
            controlnet_args_unit1.model = 'control_v11p_sd15_normalbae'
            controlnet_args_unit1.module = 'normal_bae'
            controlnet_args_unit1.pixel_perfect = True
            controlnet_args_unit1.resize_mode = 'Crop and Resize'
            controlnet_args_unit1.processor_res = 512
            controlnet_args_unit1.threshold_a = 64
            controlnet_args_unit1.threshold_b = 64
            controlnet_args_unit1.weight = 1
            # controlnet_args_unit1.weight = 0.4
            controlnet_args_unit2 = copy.deepcopy(controlnet_args_unit1)
            controlnet_args_unit2.enabled = False
            controlnet_args_unit3 = copy.deepcopy(controlnet_args_unit1)
            controlnet_args_unit3.enabled = False
            # adetail
            adetail_enabled = not cmd_opts.disable_adetailer
            face_args = {'ad_model': 'face_yolov8m.pt', 'ad_prompt': '', 'ad_negative_prompt': '', 'ad_confidence': 0.3,
                         'ad_mask_min_ratio': 0, 'ad_mask_max_ratio': 1, 'ad_x_offset': 0, 'ad_y_offset': 0,
                         'ad_dilate_erode': 4, 'ad_mask_merge_invert': 'None', 'ad_mask_blur': 4,
                         'ad_denoising_strength': 0.4,
                         'ad_inpaint_only_masked': True, 'ad_inpaint_only_masked_padding': 32,
                         'ad_use_inpaint_width_height': False, 'ad_inpaint_width': 512, 'ad_inpaint_height': 512,
                         'ad_use_steps': False, 'ad_steps': 28, 'ad_use_cfg_scale': False, 'ad_cfg_scale': 7,
                         'ad_use_noise_multiplier': False, 'ad_noise_multiplier': 1, 'ad_restore_face': False,
                         'ad_controlnet_model': 'None', 'ad_controlnet_module': 'inpaint_global_harmonious',
                         'ad_controlnet_weight': 1, 'ad_controlnet_guidance_start': 0, 'ad_controlnet_guidance_end': 1,
                         'is_api': ()}
            hand_args = {'ad_model': 'hand_yolov8s.pt', 'ad_prompt': '', 'ad_negative_prompt': '', 'ad_confidence': 0.3,
                         'ad_mask_min_ratio': 0, 'ad_mask_max_ratio': 1, 'ad_x_offset': 0, 'ad_y_offset': 0,
                         'ad_dilate_erode': 4, 'ad_mask_merge_invert': 'None', 'ad_mask_blur': 4,
                         'ad_denoising_strength': 0.4,
                         'ad_inpaint_only_masked': True, 'ad_inpaint_only_masked_padding': 32,
                         'ad_use_inpaint_width_height': False, 'ad_inpaint_width': 512, 'ad_inpaint_height': 512,
                         'ad_use_steps': False, 'ad_steps': 28, 'ad_use_cfg_scale': False, 'ad_cfg_scale': 7,
                         'ad_use_noise_multiplier': False, 'ad_noise_multiplier': 1, 'ad_restore_face': False,
                         'ad_controlnet_model': 'None', 'ad_controlnet_module': 'inpaint_global_harmonious',
                         'ad_controlnet_weight': 1, 'ad_controlnet_guidance_start': 0, 'ad_controlnet_guidance_end': 1,
                         'is_api': ()}
            sam_args = [0,
                        adetail_enabled, face_args, hand_args,  # adetail args
                        controlnet_args_unit1, controlnet_args_unit2, controlnet_args_unit3,  # controlnet args
                        True, False, 0, _input_image,
                        sam_result_tmp_png_fp,
                        0,  # sam_output_chosen_mask
                        False, [], [], False, 0, 1, False, False, 0, None, [], -2, False, [],
                        '<ul>\n<li><code>CFG Scale</code>should be 2 or lower.</li>\n</ul>\n',
                        True, True, '', '', True, 50, True, 1, 0, False, 4, 0.5, 'Linear', 'None',
                        f'<p style="margin-bottom:0.75em">Recommended settings: Sampling Steps: 80-100, Sampler: Euler a, Denoising strength: {denoising_strength}</p>',
                        128, 8, ['left', 'right', 'up', 'down'], 1, 0.05, 128, 4, 0, ['left', 'right', 'up', 'down'],
                        False, False, 'positive', 'comma', 0, False, False, '',
                        '<p style="margin-bottom:0.75em">Will upscale the image by the selected scale factor; use width and height sliders to set tile size</p>',
                        64, 0, 2, 1, '', [], 0, '', [], 0, '', [], True, False, False, False, 0, None, None, False,
                        None, None,
                        False, None, None, False, 50
                        ]

            res = modules.img2img.img2img(task_id, 4, sd_positive_prompt, sd_negative_prompt, prompt_styles, init_img,
                                          sketch,
                                          init_img_with_mask, inpaint_color_sketch, inpaint_color_sketch_orig,
                                          init_img_inpaint, init_mask_inpaint,
                                          steps, sampler_index, mask_blur, mask_alpha, inpainting_fill, restore_faces,
                                          tiling,
                                          n_iter, batch_size, cfg_scale, image_cfg_scale, denoising_strength, seed,
                                          subseed,
                                          subseed_strength, seed_resize_from_h, seed_resize_from_w, seed_enable_extras,
                                          selected_scale_tab, height, width, scale_by, resize_mode, inpaint_full_res,
                                          inpaint_full_res_padding, inpainting_mask_invert, img2img_batch_input_dir,
                                          img2img_batch_output_dir, img2img_batch_inpaint_mask_dir,
                                          override_settings_texts,
                                          *sam_args)
        except Exception:
            logging(
                f"[SAM predict fatal error][{datetime.datetime.now()}]:"
                f"{traceback.format_exc()}",
                f"logs/error.log")
        return res[0], res[0], gr.Radio.update(
            choices=[str(x) for x in range(1 if len(res[0]) == 1 else len(res[0]) - 1)], value=0), gr.Button.update(
            interactive=True), 'done.'

    def show_masks(self, image_np, masks: np.ndarray, alpha=0.5):
        image = copy.deepcopy(image_np)
        np.random.seed(0)
        for mask in masks:
            color = np.concatenate([np.random.random(3), np.array([0.6])], axis=0)
            image[mask] = image[mask] * (1 - alpha) + 255 * color.reshape(1, 1, -1) * alpha
        return image.astype(np.uint8)

    def create_mask_output(self, image_np, masks, boxes_filt):
        print("Creating output image")
        mask_images, masks_gallery, matted_images = [], [], []
        boxes_filt = boxes_filt.numpy().astype(int) if boxes_filt is not None else None
        for mask in masks:
            masks_gallery.append(Image.fromarray(np.any(mask, axis=0)))
            blended_image = self.show_masks(show_boxes(image_np, boxes_filt), mask)
            mask_images.append(Image.fromarray(blended_image))
            image_np_copy = copy.deepcopy(image_np)
            image_np_copy[~np.any(mask, axis=0)] = np.array([0, 0, 0, 0])
            matted_images.append(Image.fromarray(image_np_copy))
        return mask_images + masks_gallery + matted_images

    def sam_predict(self, dino_model_name, text_prompt, box_threshold, input_image):
        positive_points = []
        negative_points = []
        print("Start SAM Processing")
        if input_image is None:
            return [], "SAM requires an input image. Please upload an image first."
        image_np = np.array(input_image)
        image_np_rgb = image_np[..., :3]
        dino_enabled = True
        boxes_filt = None
        sam_predict_result = " done."
        if dino_enabled:
            boxes_filt, install_success = dino_predict_internal(input_image, dino_model_name, text_prompt,
                                                                box_threshold)
            if not install_success:
                if len(positive_points) == 0 and len(negative_points) == 0:
                    return [], f"GroundingDINO installment has failed. Check your terminal for more detail and {dino_install_issue_text}. "
                else:
                    sam_predict_result += f" However, GroundingDINO installment has failed. Your process automatically fall back to point prompt only. Check your terminal for more detail and {dino_install_issue_text}. "
        print(f"Running SAM Inference {image_np_rgb.shape}")
        predictor = SamPredictor(self.sam_model)
        predictor.set_image(image_np_rgb)
        if dino_enabled and boxes_filt.shape[0] > 1:
            sam_predict_status = f"SAM inference with {boxes_filt.shape[0]} boxes, point prompts disgarded"
            print(sam_predict_status)
            transformed_boxes = predictor.transform.apply_boxes_torch(boxes_filt, image_np.shape[:2])
            masks, _, _ = predictor.predict_torch(
                point_coords=None,
                point_labels=None,
                boxes=transformed_boxes.to(device),
                multimask_output=True)
            masks = masks.permute(1, 0, 2, 3).cpu().numpy()

        else:
            num_box = 0 if boxes_filt is None else boxes_filt.shape[0]
            num_points = len(positive_points) + len(negative_points)
            if num_box == 0 and num_points == 0:
                self.garbage_collect()
                if dino_enabled and num_box == 0:
                    return [], "It seems that you are using a high box threshold with no point prompts. Please lower your box threshold and re-try."
                return [], "You neither added point prompts nor enabled GroundingDINO. Segmentation cannot be generated."
            sam_predict_status = f"SAM inference with {num_box} box, {len(positive_points)} positive prompts, {len(negative_points)} negative prompts"
            print(sam_predict_status)
            point_coords = np.array(positive_points + negative_points)
            point_labels = np.array([1] * len(positive_points) + [0] * len(negative_points))
            box = copy.deepcopy(boxes_filt[0].numpy()) if boxes_filt is not None and boxes_filt.shape[0] > 0 else None
            masks, _, _ = predictor.predict(
                point_coords=point_coords if len(point_coords) > 0 else None,
                point_labels=point_labels if len(point_coords) > 0 else None,
                box=box,
                multimask_output=True)
            masks = masks[:, None, ...]

        # 连同区域数量最少
        masks = [masks[np.argmin([label(m)[1] for m in masks])]]
        # 最大面积
        # if len(masks) > 1:
        #     masks = [masks[np.argmax([np.count_nonzero(m) for m in masks])]]

        self.garbage_collect()
        return self.create_mask_output(image_np, masks, boxes_filt), sam_predict_status + sam_predict_result
