# coding=utf-8
# @Time : 2023/5/31 下午3:18
# @File : global_var.py

html_label = {
    'lang_selection': {'ch': '中文', 'jp': '日本語'},
    'input_image_label': {'ch': '上传图片', 'jp': '画像をアップロード'},
    'batch_size_label': {'ch': '生成图像数', 'jp': '生成画像数'},
    'output_gender_label': {'ch': '性别', 'jp': '性別'},
    'output_gender_list': {'ch': ['女', '男'], 'jp': ['女', '男']},
    'output_viewpoint_label': {'ch': '朝向', 'jp': '向き'},
    'output_viewpoint_list': {'ch': ['正面', '侧面', '背面'], 'jp': ['正', '侧', '背']},
    'model_mode_label': {'ch': '模式', 'jp': '模式'},
    'model_mode_list': {'ch': ['普通', '衣架'], 'jp': ['普通', '衣桁']},
    'output_age_label': {'ch': '年龄段', 'jp': '年齢'},
    'input_part_list': {'ch': ['上衣', '下衣'], 'jp': ['上半身', '下半身']}, # '鞋子' 'シューズ'
    'input_part_label': {'ch': '输入列表', 'jp': '入力リスト'},
    'output_age_list': {'ch': ['儿童', '青年', '中年'], 'jp': ['子ども', '青年', '中年']},
    'generate_btn_label': {'ch': '生成', 'jp': '生成'},
    'interrupt_btn_label': {'ch': '中断', 'jp': '中断'},
    'output_gallery_label': {'ch': '结果', 'jp': '結果'},
    'hires_input_gallery_label': {'ch': '候选', 'jp': '候选'},
    'hint1': {'ch': '操作步骤：\n1,在左侧框中上传服装图像，也可直接拖入本地服装图像。\n2,在画面左下方选择适合的服装属性。\n3,模式选项中，如果服装由完整的假人模特穿戴，请选择‘普通’,如果服装由衣架或者不完整躯体的假人穿戴，请选择‘衣架’。\n4,选择好服装属性后，点击‘生成’按钮，生成穿着该服装的真人模特。如果生成的图像不符合您的期望，请再多尝试生成几次。\n5,生成符合您期望的真人模特后，请点击页面上方的生成高清图像页标。\n6,选择输出分辨率和源图片后，点击‘生成高清图像’按钮。\n7,点击‘下载’按钮，把高清真人服装模特下载到本地。\n8,生成图像时，多人排队的情况下需要您耐心等待。', 'jp': '手順：\n1,左のボックスにコスチューム画像をアップロードするか、ローカルのコスチューム画像を直接ドラッグします。\n2,画面左下のコスチューム属性を選択してください。\n3,‘模式’オプションで、衣装が完全なダミーマネキンに着用される場合は‘普通’を選択し、衣装がハンガーまたは胴体が不完全なダミーに着用される場合は‘衣桁’を選択します。\n4,服の属性を選択した後、生成ボタンをクリックすると、その服を着た生きたモデルが生成されます。 生成された画像が期待に沿わない場合は、もう数回生成してみてください。。\n5,ご満足いただける画像を生成した後、ページ上部の「高解像度画像の生成」ページアイコンをクリックしてください。\n6,出力解像度とソース画像を選択した後、「高解像度画像の生成」ボタンをクリックします。\n7,「ダウンロード」ボタンをクリックすると、HDリアル人体模型があなたのローカルエリアにダウンロードされます。\n8,「画像を生成する際、複数のキューがある場合は我慢する必要があります。'},
    'hint2': {'ch': '输入图像的注意事项：\n1,图像中的模特，服装和背景，请尽量保持三者颜色不同。\n2,图像中尽量不要遮挡需要展示的服装。\n3,图像中的服装尽量不要透明。\n4,如果生成的图像不符合您的期望，请再多尝试生成几次。\n5,支持的输入图像格式为：JPG、JPEG、PNG、BMP。\n6,图像中尽量只展示一件衣服。', 'jp': '画像入力の注意点：\n1,画像内のモデル、衣類、背景の色を異ならせてください。\n2,画像内の衣類をブロックしないでください。\n3,衣類が透けないようにしてください。\n4,生成された画像がご期待に添えない場合は、もう数回生成してください。\n5,入力画像フォーマット：JPG、JPEG、PNG、BMP。\n6,画像に表示される衣服は1着のみであることが理想です。'},
    'choosing_index_4_hires_label': {'ch': '选择源图片', 'jp': 'ソース画像の選択'},
    'generate_hires_label': {'ch': '生成高清图像', 'jp': '高解像度画像の生成'},
    'ai_model_label': {'ch': '生成真人模特', 'jp': 'ライブ・モデルの生成'},
    'output_resolution_label': {'ch': '输出分辨率', 'jp': '出力解像度'},
    'output_resolution_list': ['1024x2048(1:2)', '2048x4096(1:2)', '1024x1536(2:3)', '2048x3072(2:3)', '2048x2048(1:1)', '2048x2560(4:5)', '2048x2632(7:9)'],
    'hires_result_image_label': {'ch': '高分辨率图像', 'jp': '高解像度画像'},
}
