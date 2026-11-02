# 原创简洁 3D 小狗动作预览

本页独立于聊天程序，只在本机预览，不读取聊天数据、不调用模型。

用户于 2026-11-02 明确选择先用简洁的真 3D 卡通小狗验证自然转头、自主动作，后续细化毛发。旧图片分层方案保留作对比，不接入聊天页。

模型由本项目 `model.js` 原创构建：平滑并集隐式表面，经 marching tetrahedra 生成一张连续皮肤，覆盖头、脖子、躯干、坐姿四肢和耳朵；Root/Spine/Neck/Head 四骨骼和连续蒙皮权重驱动，不旋转或切换头部图片。尾巴另有连续网格及五骨骼链。眼睛、鼻子和内耳为附属三维几何；眨眼通过缩放眼睛实现。当前无毛发、非高精度雕刻。

功能：鼠标跟随、方向键、触摸拖动、点击摸摸、随机看向周围/嗅闻/抬头/摇尾、间隔眨眼、侧面查看、暂停、自主动作开关、减少动态效果、隐藏页停止渲染。WebGL 2 必需。

Three.js 0.180.0 从官方 npm 分发包固定版本复制到 vendor，MIT 许可随附 `vendor/THREE-LICENSE.txt`。代码通过 import map 仅加载本地依赖，运行时无需联网。官方文档：https://threejs.org/docs/ 。

曾考察 Quaternius 的 CC0 柴犬（https://poly.pizza/m/y4wdQpg767 和 https://quaternius.com/packs/ultimateanimatedanimals.html），但作者下载来源返回 Google Drive 限额；因此未使用、未分发其模型，不应误标本模型为 Quaternius 作品。
