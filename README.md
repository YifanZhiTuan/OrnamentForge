当前 V1 主要面向：
- 中国传统纹饰
- 陶瓷刻花
- 陶瓷浅浮雕 / 浮雕
- 彩绘陶瓷
- 连续装饰纹样
- 平面、圆柱、瓷盘、简单旋转体花瓶等载体
最终目标是：
用户给一张参考图，或者只说一句话，OrnamentForge 可以把纹饰继续转化为可编辑的 3D 陶瓷资产。

1. 功能
1.1 参考图模式
如果用户已经有纹样参考图，OrnamentForge 会优先走 Fidelity Reconstruction 路线。
Reference Image
↓
Fidelity Reconstruction
↓
PlanarMaster
↓
SurfaceMap / Craft
↓
Blender

主要目标是尽量保留：
- 原始花型
- 主体位置
- 元素比例
- 构图关系
- 线条结构
- 主次层级
- 彩绘任务中的颜色关系
- 来源、Hash 与 Provenance
参考图存在时，不会为了方便建模默认重新设计纹样。
适用于：
- 黑白线稿
- 彩色纹样
- 传统陶瓷纹饰
- 花鸟纹样
- 几何纹样
- 刻花参考图
- 浮雕参考图
- 彩绘参考图
1.2 自然语言模式
没有参考图时，可以直接用一句话描述需要的纹饰。
例如：
帮我做一个双龙戏珠的青白瓷花瓶刻花，
双龙围绕中央宝珠，传统一些但不要太俗。

OrnamentForge 会调用当前 Codex 会话中的图像生成能力，先生成二维纹饰设计，再进入后续建模流程。
Natural Language
↓
Codex Image Generation
↓
生成二维纹饰候选
↓
选择纹饰母版
↓
Fidelity Reconstruction
↓
PlanarMaster
↓
SurfaceMap / Craft
↓
Blender

AI 在这一流程中的主要作用是：
负责前期纹饰设计。

后面的结构重建、曲面映射、工艺表达和 Blender 输出由 OrnamentForge 工作流继续完成。
如果当前 Codex 会话没有可调用的图像生成能力，会返回：
AI_IMAGE_TOOL_UNAVAILABLE / HOLD

不会自动切换到内部数据库，也不会偷偷使用其他设计路线。
1.3 陶瓷刻花
支持将线稿和装饰纹样转换成真实浅刻 / 阴刻效果。
主要路线：
Line Art
↓
Mask / Engraving Field
↓
SurfaceMap
↓
P - depth × N
↓
真实刻槽几何

适合：
- 细线传统纹样
- 花鸟线稿
- 祥云
- 回纹
- 羽毛
- 枝叶
- 高密度装饰图案
高密度纹样可以使用 EngravingField 路线，不要求所有线条必须先转换成完全干净的独立 Curve。
1.4 浮雕
支持把参考纹样中的视觉层级转换成几何高低关系。
例如：
主体
→ 较高层

次级花瓣 / 叶片
→ 中层

细节纹理 / 枝线
→ 较浅层

支持：
- 浅浮雕
- 分层浮雕
- 花卉浮雕
- 彩色参考图转单色浮雕
- 彩绘 + 浮雕组合表现
最终使用真实 Blender 几何 / Shape Key / Modifier 等方式保留可编辑性。
1.5 彩绘陶瓷
对于彩色参考图，可以保留：
- 原始纹样结构
- 主要颜色关系
- 元素布局
- 原图比例
然后将其映射到陶瓷表面。
适用于：
- 彩色传统纹样
- 彩绘瓷盘
- 彩绘花瓶
- 彩绘浮雕组合
注意：
彩绘本身可能以贴图方式保留，因此“模型可编辑”不等于每一个彩色色块都会被自动转换成独立矢量几何。
1.6 SurfaceMap
当前支持的主要载体：
- Plane / 平面
- Cylinder / 圆柱
- Cone / 圆锥
- Simple Revolution Vase / 简单旋转体花瓶
- Plate / Shallow Bowl 的既有映射能力
- 有限 Existing UV Mesh
SurfaceMap 会保留：
- 显式 Seam
- UV / 参数域对应关系
- Tu / Tv / Normal
- 映射来源
- Distortion QA
明显失真时会进入 HOLD，而不是强行输出。
1.7 青白瓷 / 影青材质
OrnamentForge 内置经过实际测试的陶瓷展示预设。
包括：
QINGBAI_GLAZE
YINGQING_GLAZE

主要表现：
- 青白釉基础色
- 柔和透明釉感
- Clear Coat
- 刻槽积釉
- 青绿色凹槽层次
- Window Reflection
- Rim Highlight
- Grazing Light
- AgX 色彩管理
材质只负责最终视觉表现，不会静默修改纹样几何。
2. 安装方式
环境要求
建议环境：
Python 3.11+
Blender 4.2+
Codex

当前开发与主要验证环境使用过：
Blender 5.1.2

方法一：Git Clone
进入你的 Codex 项目：
git clone https://github.com/YifanZhiTuan/OrnamentForge.git .agents/skills/ornamentforge

然后在 Codex 中调用：
$ornamentforge

方法二：下载 Skill
进入：
GitHub → Releases

下载：
ornamentforge-v1-two-input-routes.skill.zip

解压后，Skill 根目录应该能直接看到：
SKILL.md
agents/
references/
scripts/

将整个 OrnamentForge Skill 放入 Codex 可读取的 Skill 目录。
Python 环境
建议在 Skill 文件夹外创建独立 Python 环境。
安装依赖：
pip install -r scripts/requirements.txt

初始化工作目录：
python scripts/run.py --workspace <WORKSPACE> init

检查 CLI：
python scripts/run.py --workspace <WORKSPACE> cli --help

详细配置请阅读：
references/setup.md

3. 使用方式
启动 Codex 后调用：
$ornamentforge

然后直接像正常用户一样描述需求即可。
有参考图
上传图片，然后说：
使用 $ornamentforge。

按照我上传的参考图做成陶瓷刻花。
尽量保持原来的花型、比例和构图，
不要重新设计。

最后输出 Blender 可编辑文件和成品效果图。

没有参考图
直接描述：
使用 $ornamentforge。

帮我做一个双龙戏珠的青白瓷花瓶刻花，
双龙围着中央宝珠，
传统一点，但整体精致一些。

最后给我 Blender 可编辑文件和成品图。

OrnamentForge 会自行完成：
自然语言
→ AI 二维纹饰设计
→ Fidelity
→ 建模
→ Blender

4. 示例提示词
双龙戏珠花瓶
使用 $ornamentforge。

帮我做一个双龙戏珠的青白瓷花瓶刻花，
双龙围着中间的宝珠，
传统一点但不要太俗，纹样精致一些。

最后给我可编辑 Blender 文件，
再出正面、3/4 和细节图。

莲花团花瓷盘
使用 $ornamentforge。

做一个莲花团花的青白瓷盘。

中心一朵莲花，
四周配莲叶和枝蔓，
整体对称舒服一点，不要塞得太满。

做成浅刻效果，
最后给 Blender 文件和成品图。

连续祥云陶瓷杯
使用 $ornamentforge。

帮我做一个青白瓷杯，
杯身绕一圈连续祥云纹。

简单一些，
接缝位置不要明显。

纹样做浅刻，
最后输出 Blender 和效果图。

参考图刻花
使用 $ornamentforge。

就按我上传的这张图做，
不要重新设计。

尽量把纹样的位置、比例和细节保留下来，
然后做成陶瓷刻花。

最后输出可编辑 Blender 文件和效果图。

彩色参考图转浮雕
使用 $ornamentforge。

把我上传的彩色纹样做成陶瓷浮雕。

花型和整体布局不要改。

颜色可以用来帮助理解主次关系，
再把这些视觉层次转换成浮雕的高低起伏。

最后输出 Blender 可编辑文件和效果图。

彩绘 + 浮雕
使用 $ornamentforge。

把我这张彩色纹样做成陶瓷彩绘浮雕。

保留原来的颜色、花型和布局，
同时根据纹样层次生成不同高度的浮雕。

最后输出 Blender 可编辑文件和成品图。

5. 当前限制
OrnamentForge V1 不是一个：
“输入任意一句话就可以生成任意 3D 模型”

的通用系统。
当前主要限制包括：
- 不支持任意自由曲面自动展开
- 不提供通用 Automatic UV Unwrap
- Sphere 尚未作为正式 SurfaceMap V1 能力
- 不支持自动 Multi-chart
- 不提供复杂自动 Seam 优化
- 不提供通用全局测地线求解
- 不保证任意自由曲面花瓶都能自动映射
- 不提供制造级模具验证
- 不预测真实陶瓷烧成结果
- 不自动判断纹样历史年代真实性
- AI 生成纹样仍可能存在视觉错误
- 极细线稿可能产生采样锯齿或局部细节损失
- 彩绘参考图的光照、釉面反射可能影响最终颜色观感
遇到无法可靠完成的任务时可能返回：
HOLD

或：
NOT_SUPPORTED

这是 OrnamentForge 的正常质量控制行为。
Skill 不会为了强行生成结果而自动降低 QA 标准。
6. License
OrnamentForge 使用分离式授权。
代码
以下内容采用：
MIT License

包括：
- Python 代码
- SKILL.md
- scripts
- 项目编写的 references
- CLI 与运行逻辑
正式许可证见：
LICENSE

原创纹样资产
仓库内明确标记为项目原创并允许再分发的纹样和几何资产采用：
Creative Commons Attribution 4.0 International
CC BY 4.0

允许：
- 使用
- 修改
- 再分发
- 商业使用
但需要保留必要的：
- 作者信息
- 来源信息
- Attribution
- 修改说明
详细内容：
LICENSE-ASSETS.md

第三方依赖
所有第三方库继续遵循其自己的许可证。
详见：
THIRD_PARTY_NOTICES.md

不包含在开源授权中的内容
本仓库的授权不会自动覆盖：
- ArtLibrary 原始资料
- 第三方传统纹饰图片
- 用户上传参考图
- AI 生成测试图片
- 历史 runs
- Blender 最终展示资产
- 用户后续自行生成的作品
这些内容的版权与使用权由其原始来源决定。
当前版本
OrnamentForge v1.0.0

V1 当前核心只有两种入口：
参考图
→ Fidelity
→ 3D

自然语言
→ Codex Image Design
→ Fidelity
→ 3D

目前已经完成多组黑盒测试，包括：
- 双龙戏珠青白瓷花瓶
- 莲花团花瓷盘
- 连续祥云陶瓷杯
- 黑白花鸟参考图刻花
- 彩色纹样彩绘
- 彩色纹样浮雕
- 彩绘 + 浮雕
关于项目
OrnamentForge 是「一番纸团 / YifanZhiTuan」复杂纹饰数字化方向的实验性开源项目。
希望探索：
如何让传统纹饰不只停留在一张生成图片里，而能够进一步成为可编辑、可映射、可继续创作的数字 3D 资产。

后续将根据真实使用反馈继续完善：
- Fidelity
- 曲面映射
- 刻花质量
- 浮雕结构
- 材质表现
- 更多器型适配
Created by 一番纸团 / YifanZhiTuan

---

# ② `LICENSE.zh-CN.md`

这个是给中文用户看的 **MIT 中文说明**。

注意顶部一定写：

> **本文件仅用于中文阅读，法律效力以根目录 LICENSE 英文原文为准。**

内容：

```markdown
# MIT License 中文说明

> 本文件仅作为中文阅读说明。  
> 正式授权条款以仓库根目录中的 `LICENSE` 英文原文为准。

Copyright (c) 2026 YifanZhiTuan

MIT License 允许任何人在获得本软件及相关文档后，自由地：

- 使用
- 复制
- 修改
- 合并
- 发布
- 分发
- 再授权
- 销售软件副本

同时也允许获得软件的人继续进行上述行为。

唯一的主要要求是：

在软件的重要部分或副本中，需要保留原始的版权声明以及 MIT License 授权声明。

---

## 免责声明

本软件按“现状”提供，不附带任何明示或暗示的保证，包括但不限于：

- 适销性
- 特定用途适用性
- 不侵权保证

在任何情况下，作者或版权持有人均不对因本软件或本软件使用而产生的任何：

- 索赔
- 损害
- 责任

承担责任。

---

## 正式许可

请以：

`LICENSE`

中的英文 MIT License 原文为正式法律文本。

③ LICENSE-ASSETS.zh-CN.md
这个是你原创 Motif / 几何资产的中文说明：
# OrnamentForge 原创资产授权中文说明

> 本文件仅用于帮助中文用户理解资产授权。  
> 正式授权范围与法律条款以 `LICENSE-ASSETS.md` 以及 CC BY 4.0 官方授权文本为准。

OrnamentForge 中明确标记为项目原创并允许公开再分发的：

- MotifRecord
- 原创纹样数据
- 可复用几何结构
- 项目原创装饰资产

采用：

**Creative Commons Attribution 4.0 International（CC BY 4.0）**

进行授权。

---

## 你可以做什么

在遵守 CC BY 4.0 条件的情况下，你可以：

- 使用这些资产
- 复制这些资产
- 修改这些资产
- 二次创作
- 将其用于其他项目
- 再分发
- 商业使用

---

## 你需要做什么

使用这些资产时，需要保留合理的署名信息。

例如：

```text
Original ornament assets from OrnamentForge
by YifanZhiTuan
Licensed under CC BY 4.0

如果你对原资产进行了修改，也应当合理说明：
该资产基于 OrnamentForge 原始资产进行了修改。

哪些内容不属于这个授权
CC BY 4.0 不自动覆盖：
- ArtLibrary 中的外部资料
- 第三方纹样图片
- 历史艺术作品图片
- 用户自己上传的参考图
- AI 测试图片
- 历史运行结果
- Blender 最终展示成品
- 未明确声明为 OrnamentForge 原创资产的文件
这些内容仍然按照其原始来源的版权和授权规则处理。
用户自己的生成结果
用户通过 OrnamentForge 使用自己提供的：
- 参考图
- 素材
- 图片
- 第三方数据
生成的结果，不会因为使用 OrnamentForge 就自动变成 CC BY 4.0。
用户需要自行确保其输入内容具有合法使用权。
正式授权文本
请参阅：
LICENSE-ASSETS.md
以及 Creative Commons 官方：
Creative Commons Attribution 4.0 International
正式法律文本。

---

### GitHub 最终就会变成

```text
README.md                     ← 中文项目主页
LICENSE                       ← 正式 MIT 英文
LICENSE.zh-CN.md              ← MIT 中文说明

LICENSE-ASSETS.md             ← 正式资产授权
LICENSE-ASSETS.zh-CN.md       ← 资产授权中文说明

THIRD_PARTY_NOTICES.md
SKILL.md
...
