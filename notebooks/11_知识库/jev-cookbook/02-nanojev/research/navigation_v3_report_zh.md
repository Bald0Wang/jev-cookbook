# Navigation V3 固定实验报告

生成时间：2026-09-17T15:25:00.803913+00:00。

**结果齐全，已完成独立核验。**

预定主模型 greedy 的 test／OOD 完成率为 90%／55%，T=1 采样为 90%／75%；对应采样路径效率为 0.8356／0.6213。

主模型采样相对均匀随机的 OOD 完成率差为 0.0500 [-0.2000, 0.2500]，路径效率差为 0.5085 [0.3129, 0.6859]。本次结果支持路径效率改善，尚不足以确认陌生地图通关率稳定提高。

四组 gold 对照中，显式坐标对 greedy 完成率的平均影响为 test 0.5500 [0.3250, 0.7500]、OOD 0.3000 [0.1000, 0.4750]。多起点覆盖没有表现为普遍收益，完整主效应与交互见下表。

次要教师分布监督模型在采样下完成 test 95%、OOD 90%；OOD 路径效率为 0.5442。其完成率点值高于主 gold 模型，效率点值较低；当前配对区间不足以判定教师目标总体优于 gold 目标。

主展示预先固定为 `v3_gold_coords_multi_seed17`。四个 gold 模型组成输入表示（ASCII／坐标）×训练起点覆盖（single／multi）的 2×2 对照；同表示的教师分布监督是次要对照。未依据 test 或 OOD 改默认模型、温度、控制器或训练设置。

四个 gold 模型都使用 300 张训练地图×8 个 D4 呈现槽，共 2400 条导航训练曝光，加 984 条相同非导航 replay；单起点为每原始地图 1 个起点，多起点共 1874 个原始起点。每组都从同一 V2 teacher seed 17 权重恢复，用新优化器训练 1200 步、head warmup 0 步。single 的 8 次 D4 呈现不代表 8 个不同原始起点。

只有 1 个训练 seed，不能估计训练随机性的方差。95% 区间按完整源地图进行 500 次配对 bootstrap，反映固定 checkpoint、固定采样种子下的地图采样不确定性；不覆盖训练 seed 或控制器 RNG 的变化。区间未作多重比较校正。

## 固定闭环协议与覆盖

test 与 OOD 各取冻结文件顺序中前 20 张不同的可达、非终局地图，所有策略使用相同初始状态；共有 40 张地图，与训练源地图重叠 0。每局最多 `2×size²` 步，保留所有成功和失败。单合法动作直接执行并另计，不调用模型；其余活跃状态每个 tick 一次批量 forward。

greedy 取原始概率最大动作；sample 从完整原始 T=1 分布采样。各 episode 使用 stable-hash 派生的独立 RNG，强制步不消耗随机数。不添加访问惩罚、epsilon、温度调优、循环提前终止或 oracle 兜底。原始概率、随机数和实际动作全部保存并独立重放核验。

路径效率为成功时最短距离／实际步数，失败为 0。重复访问率为已访问目的格所占步数，初始格也计为已访问。p(optimal) 和实际最优动作率只统计非强制决策，按决策步数加权。它们与最终通关率分别报告；p(optimal) 是策略在 BFS 最优动作集合上的质量，不能视为通关概率。

闭环 p(optimal) 还受到各控制器实际访问状态的影响；不同控制器之间的差值不是在同一固定状态集合上的能力差。下方离线指标则使用相同冻结状态。

V3 与 V2 使用不同地图集合、表示和训练安排，本报告不将两版数字直接作胜负比较。

| 模型／控制器 | 分区 | 完成率 | 路径效率 | 平均步数 | 重复访问率 | p(optimal) | 实际最优率 | 强制步 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| random | test | 0.7000 | 0.1399 | 17.6500 | 0.6657 | 0.5155 | 0.5046 | 26 |
| random | ood | 0.7000 | 0.1127 | 43.8000 | 0.7386 | 0.4853 | 0.5000 | 54 |
| oracle | test | 1.0000 | 1.0000 | 2.3000 | 0.0000 | 1.0000 | 1.0000 | 0 |
| oracle | ood | 1.0000 | 1.0000 | 4.2500 | 0.0000 | 1.0000 | 1.0000 | 0 |
| v3_gold_ascii_single_seed17/greedy | test | 0.5000 | 0.5000 | 17.0500 | 0.8680 | 0.5371 | 0.3783 | 74 |
| v3_gold_ascii_single_seed17/greedy | ood | 0.3000 | 0.3000 | 51.2500 | 0.9346 | 0.6294 | 0.4021 | 177 |
| v3_gold_ascii_single_seed17/sample | test | 0.7500 | 0.2956 | 15.4000 | 0.7078 | 0.5258 | 0.4964 | 30 |
| v3_gold_ascii_single_seed17/sample | ood | 0.7000 | 0.3729 | 32.0500 | 0.7441 | 0.5146 | 0.5000 | 45 |
| v3_gold_ascii_multi_seed17/greedy | test | 0.2000 | 0.2000 | 25.9000 | 0.9382 | 0.5063 | 0.4555 | 46 |
| v3_gold_ascii_multi_seed17/greedy | ood | 0.0500 | 0.0500 | 68.5000 | 0.9686 | 0.5246 | 0.4820 | 36 |
| v3_gold_ascii_multi_seed17/sample | test | 0.7000 | 0.1399 | 17.6500 | 0.6657 | 0.5155 | 0.5046 | 26 |
| v3_gold_ascii_multi_seed17/sample | ood | 0.7000 | 0.1127 | 43.8000 | 0.7386 | 0.4851 | 0.5000 | 54 |
| v3_gold_coords_single_seed17/greedy | test | 0.9000 | 0.9000 | 5.0000 | 0.6000 | 0.6937 | 0.7000 | 0 |
| v3_gold_coords_single_seed17/greedy | ood | 0.4000 | 0.4000 | 44.1500 | 0.9513 | 0.5136 | 0.4947 | 36 |
| v3_gold_coords_single_seed17/sample | test | 1.0000 | 0.9386 | 3.4000 | 0.2500 | 0.8330 | 0.8382 | 0 |
| v3_gold_coords_single_seed17/sample | ood | 0.7000 | 0.5607 | 27.3500 | 0.8282 | 0.5042 | 0.5137 | 37 |
| v3_gold_coords_multi_seed17/greedy | test | 0.9000 | 0.9000 | 5.1000 | 0.5784 | 0.7489 | 0.6163 | 16 |
| v3_gold_coords_multi_seed17/greedy | ood | 0.5500 | 0.5500 | 33.9000 | 0.9277 | 0.4937 | 0.4984 | 36 |
| v3_gold_coords_multi_seed17/sample | test | 0.9000 | 0.8356 | 5.9000 | 0.5593 | 0.6987 | 0.6404 | 4 |
| v3_gold_coords_multi_seed17/sample | ood | 0.7500 | 0.6213 | 25.1000 | 0.7988 | 0.5380 | 0.5224 | 33 |
| v3_teacher_coords_multi_seed17/greedy | test | 0.9000 | 0.9000 | 5.0000 | 0.6100 | 0.7051 | 0.6800 | 0 |
| v3_teacher_coords_multi_seed17/greedy | ood | 0.5000 | 0.5000 | 37.5500 | 0.9361 | 0.4857 | 0.4425 | 107 |
| v3_teacher_coords_multi_seed17/sample | test | 0.9500 | 0.8250 | 4.7500 | 0.4526 | 0.7997 | 0.7033 | 4 |
| v3_teacher_coords_multi_seed17/sample | ood | 0.9000 | 0.5442 | 22.6500 | 0.7550 | 0.5416 | 0.5519 | 29 |

## 预定主模型与配对差值

以下为点估计及 95% bootstrap 区间。差值严格按表中方向；完成率、效率越高越好，重复访问率越低越好。JSON 包含全部固定 2×2 主效应、交互、次要教师对照和各模型 sample−greedy 的配对区间。

| 预定比较 | 分区 | 完成率／差值 [CI] | 路径效率／差值 [CI] | 重复访问率／差值 [CI] |
|---|---|---|---|---|
| v3_gold_coords_multi_seed17/greedy | test | 0.9000 [0.7500, 1.0000] | 0.9000 [0.7500, 1.0000] | 0.5784 [0.0000, 0.7684] |
| v3_gold_coords_multi_seed17/greedy | ood | 0.5500 [0.3238, 0.7500] | 0.5500 [0.3238, 0.7500] | 0.9277 [0.8655, 0.9541] |
| v3_gold_coords_multi_seed17/sample | test | 0.9000 [0.7500, 1.0000] | 0.8356 [0.6688, 0.9800] | 0.5593 [0.0235, 0.7008] |
| v3_gold_coords_multi_seed17/sample | ood | 0.7500 [0.5500, 0.9262] | 0.6213 [0.4229, 0.8008] | 0.7988 [0.6876, 0.8452] |
| greedy/primary_minus_random | test | 0.2000 [0.0500, 0.4000] | 0.7601 [0.6278, 0.8682] | -0.0873 [-0.6686, 0.0951] |
| greedy/primary_minus_random | ood | -0.1500 [-0.4000, 0.0500] | 0.4373 [0.2174, 0.6320] | 0.1891 [0.1210, 0.2441] |
| sample/primary_minus_random | test | 0.2000 [0.0500, 0.4000] | 0.6957 [0.5437, 0.8230] | -0.1064 [-0.5862, 0.0046] |
| sample/primary_minus_random | ood | 0.0500 [-0.2000, 0.2500] | 0.5085 [0.3129, 0.6859] | 0.0602 [-0.0531, 0.1230] |
| greedy/mean_coordinates_effect | test | 0.5500 [0.3250, 0.7500] | 0.5500 [0.3250, 0.7500] | -0.3139 [-0.8824, -0.1208] |
| greedy/mean_coordinates_effect | ood | 0.3000 [0.1000, 0.4750] | 0.3000 [0.1000, 0.4750] | -0.0121 [-0.0524, 0.0089] |
| greedy/mean_multi_effect | test | -0.1500 [-0.2750, -0.0250] | -0.1500 [-0.2750, -0.0250] | 0.0243 [-0.2713, 0.3237] |
| greedy/mean_multi_effect | ood | -0.0500 [-0.1750, 0.0750] | -0.0500 [-0.1750, 0.0750] | 0.0052 [-0.0186, 0.0207] |
| greedy/interaction | test | 0.3000 [0.0500, 0.5500] | 0.3000 [0.0500, 0.5500] | -0.0918 [-0.6776, 0.5295] |
| greedy/interaction | ood | 0.4000 [0.2000, 0.6500] | 0.4000 [0.2000, 0.6500] | -0.0576 [-0.1173, -0.0252] |
| sample/mean_coordinates_effect | test | 0.2250 [0.1000, 0.3750] | 0.6694 [0.5533, 0.7685] | -0.2821 [-0.6167, -0.1661] |
| sample/mean_coordinates_effect | ood | 0.0250 [-0.1000, 0.1631] | 0.3481 [0.2004, 0.4823] | 0.0721 [0.0049, 0.1116] |
| sample/mean_multi_effect | test | -0.0750 [-0.1750, 0.0250] | -0.1294 [-0.2118, -0.0488] | 0.1336 [-0.0107, 0.2191] |
| sample/mean_multi_effect | ood | 0.0250 [-0.1000, 0.1500] | -0.0998 [-0.2180, 0.0079] | -0.0175 [-0.0805, 0.0636] |
| sample/interaction | test | -0.0500 [-0.2762, 0.1500] | 0.0526 [-0.1337, 0.2285] | 0.3514 [0.0973, 0.5028] |
| sample/interaction | ood | 0.0500 [-0.3000, 0.3500] | 0.3208 [0.0615, 0.5929] | -0.0238 [-0.1679, 0.1272] |
| greedy/secondary_teacher_minus_gold | test | 0.0000 [-0.1500, 0.1500] | 0.0000 [-0.1500, 0.1500] | 0.0316 [-0.5925, 0.6000] |
| greedy/secondary_teacher_minus_gold | ood | -0.0500 [-0.2000, 0.1262] | -0.0500 [-0.2000, 0.1262] | 0.0084 [-0.0306, 0.0472] |
| sample/secondary_teacher_minus_gold | test | 0.0500 [0.0000, 0.1500] | -0.0106 [-0.1148, 0.0870] | -0.1067 [-0.2897, 0.0753] |
| sample/secondary_teacher_minus_gold | ood | 0.1500 [-0.0500, 0.3500] | -0.0770 [-0.2272, 0.0839] | -0.0438 [-0.1793, 0.0712] |

## 离线 gold 目标与教师拟合分别报告

完整离线 test 为 80 张地图×3 个起点×3 道题（720 题），OOD 为 40×3×3（360 题），包含不可达状态。它们的覆盖范围大于上面的可达闭环子集。动作 gold 是最优动作均匀策略；Boolean／Score gold 是可程序验证的确定真值。动作 CE／KL 只评价对参考策略的恢复，不能声称已经校准环境不确定性。

| 模型 | 分区 | 动作最优命中 | 动作最优质量 | 动作 gold CE | 动作 gold KL | Solvable 准确率／Brier | Value 准确率／Brier |
|---|---|---:|---:|---:|---:|---|---|
| v3_gold_ascii_single_seed17 | test | 0.6583 | 0.6746 | 0.8012 | 0.4818 | 0.7500／0.3658 | 0.3833／0.6469 |
| v3_gold_ascii_single_seed17 | ood | 0.7083 | 0.6830 | 0.8782 | 0.4883 | 0.7500／0.3600 | 0.2333／0.7797 |
| v3_gold_ascii_multi_seed17 | test | 0.5958 | 0.6316 | 0.8593 | 0.5399 | 0.7500／0.3750 | 0.3833／0.6791 |
| v3_gold_ascii_multi_seed17 | ood | 0.6333 | 0.6084 | 0.9930 | 0.6030 | 0.7500／0.3760 | 0.2333／0.8274 |
| v3_gold_coords_single_seed17 | test | 0.9542 | 0.9387 | 0.4419 | 0.1224 | 0.8833／0.2005 | 0.8542／0.2395 |
| v3_gold_coords_single_seed17 | ood | 0.7583 | 0.7434 | 1.3446 | 0.9546 | 0.8167／0.3224 | 0.5917／0.7453 |
| v3_gold_coords_multi_seed17 | test | 0.9458 | 0.8909 | 0.4979 | 0.1784 | 0.8042／0.2748 | 0.7708／0.3399 |
| v3_gold_coords_multi_seed17 | ood | 0.8000 | 0.7699 | 0.9101 | 0.5201 | 0.8167／0.2638 | 0.6000／0.6494 |
| v3_teacher_coords_multi_seed17 | test | 0.9667 | 0.9282 | 0.5060 | 0.1866 | 0.7500／0.3289 | 0.6542／0.4798 |
| v3_teacher_coords_multi_seed17 | ood | 0.8000 | 0.7695 | 0.9480 | 0.5580 | 0.7500／0.3518 | 0.4917／0.6464 |

教师拟合使用冻结坐标输入上 Jev 返回的可用原样 rounded proxy；ASCII 学生与这一教师参考比较时，教师输入仍是坐标表示，不能称作 ASCII 输入上的 Jev 实测。非归一化和缺失教师输出仅在教师指标中剔除，学生 gold 指标仍覆盖全部题。CE／KL 使用自然对数和 1e-12 概率下限；JSON 报告受下限影响的目标质量。多类 Brier 未除以类别数。

| 分区／题型 | 教师可用／总数 | 隔离无效 | 缺失 |
|---|---:|---:|---:|
| test/action | 238/240 | 1 | 1 |
| test/solvable | 239/240 | 0 | 1 |
| test/value | 238/240 | 1 | 1 |
| ood/action | 119/120 | 1 | 0 |
| ood/solvable | 120/120 | 0 | 0 |
| ood/value | 118/120 | 2 | 0 |

| 模型 | 分区／题型 | 教师覆盖题数 | 教师 TV | 教师 KL |
|---|---|---:|---:|---:|
| v3_gold_ascii_single_seed17 | test/action | 238 | 0.3550 | 0.4259 |
| v3_gold_ascii_single_seed17 | test/solvable | 239 | 0.1336 | 0.1643 |
| v3_gold_ascii_single_seed17 | test/value | 238 | 0.5266 | 1.2847 |
| v3_gold_ascii_single_seed17 | ood/action | 119 | 0.3467 | 0.4085 |
| v3_gold_ascii_single_seed17 | ood/solvable | 120 | 0.1312 | 0.1588 |
| v3_gold_ascii_single_seed17 | ood/value | 118 | 0.6107 | 2.2611 |
| v3_gold_ascii_multi_seed17 | test/action | 238 | 0.3972 | 0.4644 |
| v3_gold_ascii_multi_seed17 | test/solvable | 239 | 0.1678 | 0.1062 |
| v3_gold_ascii_multi_seed17 | test/value | 238 | 0.5359 | 1.1715 |
| v3_gold_ascii_multi_seed17 | ood/action | 119 | 0.4046 | 0.4799 |
| v3_gold_ascii_multi_seed17 | ood/solvable | 120 | 0.1756 | 0.1129 |
| v3_gold_ascii_multi_seed17 | ood/value | 118 | 0.6212 | 2.1418 |
| v3_gold_coords_single_seed17 | test/action | 238 | 0.1408 | 0.1858 |
| v3_gold_coords_single_seed17 | test/solvable | 239 | 0.2769 | 1.0034 |
| v3_gold_coords_single_seed17 | test/value | 238 | 0.4425 | 2.2398 |
| v3_gold_coords_single_seed17 | ood/action | 119 | 0.3453 | 0.8668 |
| v3_gold_coords_single_seed17 | ood/solvable | 120 | 0.2944 | 0.9721 |
| v3_gold_coords_single_seed17 | ood/value | 118 | 0.6348 | 3.7301 |
| v3_gold_coords_multi_seed17 | test/action | 238 | 0.1687 | 0.1574 |
| v3_gold_coords_multi_seed17 | test/solvable | 239 | 0.2766 | 0.5412 |
| v3_gold_coords_multi_seed17 | test/value | 238 | 0.4213 | 1.0553 |
| v3_gold_coords_multi_seed17 | ood/action | 119 | 0.3024 | 0.4217 |
| v3_gold_coords_multi_seed17 | ood/solvable | 120 | 0.2788 | 0.5195 |
| v3_gold_coords_multi_seed17 | ood/value | 118 | 0.5660 | 1.9061 |
| v3_teacher_coords_multi_seed17 | test/action | 238 | 0.0753 | 0.0398 |
| v3_teacher_coords_multi_seed17 | test/solvable | 239 | 0.0462 | 0.0145 |
| v3_teacher_coords_multi_seed17 | test/value | 238 | 0.1126 | 0.0685 |
| v3_teacher_coords_multi_seed17 | ood/action | 119 | 0.2972 | 0.4120 |
| v3_teacher_coords_multi_seed17 | ood/solvable | 120 | 0.0384 | 0.0127 |
| v3_teacher_coords_multi_seed17 | ood/value | 118 | 0.2815 | 0.3351 |

## 完整性与来源

固定 warm-start SHA-256：`231b5178098477d9f82ae2cf38786d9ab8e0a80a019f009e55b772a66882cec4`。主展示和运行配置来自训练前 launch manifest；每个结果的输入、配置、checkpoint、预测及轨迹哈希记录在 JSON。所有已加载闭环轨迹均由环境重新推进，并重放逐 episode 随机数；结果不依赖 JSON 内自报的成功率。

warm-start hash 核对的是冻结源权重和运行清单；训练器日志未另行记录加载瞬间的权重 hash。学生回放的 checkpoint hash 与训练完成后 best 权重清单逐项匹配，每步输入也按冻结 renderer 重建并核对 hash。

远端闭环使用删除 teacher／oracle 标签后的最小环境包；本地基准保留原始 canonical 文件来源。两套文件哈希分别记录，环境身份、顺序及初始状态逐项一致；不将这种序列化差异当作地图差异，也不隐藏来源变化。

离线训练结果齐全：5/5；闭环结果齐全：12/12（含两个基准）。

ASCII multi 学生在已访问状态的 1149 次采样决策中，每个候选概率与均匀分布的最大绝对差仅 0.00244141；40 局中 39 局的完整动作序列与同种子随机基准相同。学生原始概率、唯一不同轨迹与所有失败均保留。

旧非导航任务的回归测试见 [独立回归报告](navigation_v3_regression_zh.md)。它复用 V2 测试题，不属于新的未见任务评测；其中记录的 OOD 退步与本报告的新导航收益同时保留。

