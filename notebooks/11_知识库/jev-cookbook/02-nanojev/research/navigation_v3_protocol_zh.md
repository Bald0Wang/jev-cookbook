# V3 导航 2×2 与教师对照：固定协议

此协议在V3学生测试结果产生前冻结。V2结果全部保留，V2 test已见，仅作历史参照。主展示预先指定coords/multi/seed17；不按新test选择最佳view。

五个run：gold_ascii_single、gold_ascii_multi、gold_coords_single、gold_coords_multi，以及teacher_coords_multi。共同从v2_teacher_seed17最终checkpoint warm start，seed17、head0、1200full steps、batch12、micro4、max6000 padded tokens、maxlen512、BF16；不改网络或loss。各run仅按各自预定目标的新V3 dev CE选择checkpoint，test/ood只在训练与选择完成后评估。

四个gold view的300张训练地图、D4曝光槽ID及记录顺序完全一致。multi使用canonical每槽起点；single每地图按固定hash RNG选一个原始起点，同样经过8种D4。重复物理状态保留为明确exposure slot，不称新增独立数据；manifest报告unique physical states和unique original starts。相同seed和步数下，当前均匀question sampler有相同slot采样机会，loss不再乘任何weight。

表示因子只改变地图/候选的表示：ASCII没有显式坐标或候选destination，coords明确坐标、索引和合法下一格。任务说明、环境规则与程序gold语义一致。覆盖因子只改变TRAIN；新dev/calibration/test/ood的实际环境在所有view中完全相同，仅按表示因子渲染。

每view包含2400条导航train曝光记录及984条相同V2 nongrid train replay（包含TTT/workflow/support，排除所有V2 grid、旧dev/calibration/test/ood）。train共3384记录/10152题；新dev/calibration/test/ood为120/120/240/120状态；总3984记录/11952题。

只有coords_multi包保留最小化teacher字段供teacher arm和fidelity记录；gold目标不受teacher缺失/舍入隔离影响。其它gold view不需要teacher。teacher arm只排除无效teacher目标，覆盖数单列；这使teacher对照的eligible曝光与四个gold arm略有差异。

固定控制器消融：greedy、学生p采样(T=1)、uniform random，可列oracle上界；同一组新test/ood地图、固定每episode RNG和相同步数上限，保留全部失败与成功。最优动作策略分布不是成功概率，不能称实际事件校准。

相同question曝光并不等于相同token/FLOP；分别报告输入长度、训练时间与显存。此2×2可以比较表示和起点覆盖的效应及交互，但只有一个固定训练seed，仍不足以估计一般训练方差。

协议数据seed=17；canonical SHA256=7de3fe81623914e6c1cb22e3fc6015aaa30cf69883c29d4c4be4271be04e2635；V2 replay源SHA256=7294765b80e751fc5aee7aba906b28a8ea80d6f147253d3f6c3e4f491de0b2d7。原始文件均不修改。
