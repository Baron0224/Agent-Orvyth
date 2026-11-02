# 小柴犬独立互动预览

2026-11-02：用户选择先做小狗，后续可增加小猫；当前只做独立预览，不替换浏览器聊天页。

`index.html` 可直接打开；也可在此目录用 Python 静态服务器预览。无第三方前端依赖，不读取聊天记录、不调用模型。

2026-11-02 第二版：用户认为六图切换生硬，因此改成头、身体、尾巴分层的连续动画。头部通过逐帧、按时间计算的阻尼平滑跟随鼠标；不再用六方向整图切换。身体轻微呼吸；静止时约每 7–12 秒随机歪头、低头嗅闻、抬头伸展或摇尾，另有间隔眨眼。首次自主动作约 4.8 秒后出现，鼠标活跃时延后。点击有约 2.7 秒的歪头/摇尾反应，可用开关关闭自主动作。隐藏标签页时停止动画，恢复时重置计时，系统减少动态效果时停止连续运动。

当前仍是 2.5D 分层动画，小角度旋转和视差连续，但没有真实 3D 几何，不能显示自然的大角度侧脸或背面。需要那种能力时应采用带骨骼的 3D 模型。闭眼图与睁眼图之间有生成差异，后续可进一步精修。

素材 `dog-poses.png`：内置 image_gen 生成，参考本轮小猫与小狗对比图中的右侧柴犬。原图完整保留，页面用 CSS 定位展示六格，无裁剪覆盖或像素修改。

旧 `dog-poses.png` 仅保留作早期设计参考，当前渲染改用 `dog-rig.png`。新素材由内置 image_gen 编辑生成并保留透明通道：左上睁眼头部、右上闭眼头部、左下无头身体、右下尾巴；CSS 按图集位置分层合成，无栅格像素修改。

### 分层图集最终提示词（内置工具模式）

Use case: identity-preserve. Asset type: transparent layered 2D puppet parts for smooth animated desktop companion, not a pose contact sheet. Use the SAME fluffy tan-and-cream Shiba Inu puppy from the reference, preserving its charming slightly 3D furry toy aesthetic, round face, glossy dark eyes, warm tan fur, cream muzzle, tiny black nose, small friendly closed-mouth smile. Create ONE transparent PNG sheet, exactly 2 by 2 equal square cells, no background, no shadows, no borders, no labels. FOUR clean isolated puppet parts with generous transparent margins, no stray artifacts: TOP LEFT: only the puppy's full HEAD, straight frontal and upright, ears included, open eyes, no neck, no body or paws; occupy about 78 percent of cell height and 80 percent of cell width, centered, the head tapers into cream chin. TOP RIGHT: exact same HEAD at identical scale, placement and face expression but with eyes gently CLOSED in a natural relaxed blink, no neck/body, all other details precisely unchanged; both head tiles must align. BOTTOM LEFT: only the front-facing sitting puppy BODY, head completely absent, neck stump with soft cream fur, tan shoulders, cream chest and two front paws, small back paws; no tail; compact plump torso centered, paws on baseline 88 percent, neck at 20 percent; a fluffy soft neck must allow head to overlap it seamlessly. BOTTOM RIGHT: only the curled fluffy tan/cream TAIL, isolated with a narrow attachment root bottom left, curled fluffy tip pointing upper right, no body, no head; centered with transparent margins. This is a professional character rig parts sheet for compositing: the two separate heads will sit ABOVE and OVERLAP the body neck at runtime; tail behind body. Consistent front orthographic-ish camera, lighting, fur texture, colors, and edge softness across all parts. Beautiful polished subtle 3D volume and fine fur, adorable rounded animal anatomy. Transparent alpha between and around all pieces. NO completed full-body animals, NO duplicate parts inside a cell, NO extra eyes, NO text or accessories.

生成提示词要点：保持暖棕奶油色毛绒柴犬的身份；3 列 × 2 行白底；同尺度、坐姿、身体正向；依次正视、头向画面左侧、头向右侧、抬头、低头、开心歪头；轻微 3D 动画电影毛绒质感，无文字、服装或其他动物。
