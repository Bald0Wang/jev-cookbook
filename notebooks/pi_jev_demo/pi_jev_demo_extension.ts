import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { readFileSync } from "node:fs";

type ChoiceAnswer = {
	choice: string;
	probabilities?: Record<string, number>;
	confidence?: number;
};

type NoulAnswer = { noul: number };

type JevResponse = {
	model: string;
	answers: Record<string, ChoiceAnswer | NoulAnswer>;
	usage?: unknown;
};

const PREFIX = "[pi-jev-demo] ";
const SKILLS = {
	ui_implementation: "实现界面交互、组件和样式",
	accessibility: "处理键盘操作、语义结构和无障碍要求",
	documentation: "补充使用说明、示例和文档",
} as const;

function loadSkill(name: string): string {
	return readFileSync(new URL(`./skills/${name}/SKILL.md`, import.meta.url), "utf8");
}

function offlineChoice(task: string): ChoiceAnswer {
	const text = task.toLowerCase();
	const choice = /无障碍|accessib|键盘|aria|screen reader/.test(text)
		? "accessibility"
		: /文档|说明|readme|documentation/.test(text)
			? "documentation"
			: "ui_implementation";
	return {
		choice,
		confidence: 0.91,
		probabilities: {
			[choice]: 0.91,
			...Object.fromEntries(Object.keys(SKILLS).filter((key) => key !== choice).map((key) => [key, 0.045])),
		},
	};
}

function offlineGate(tool: string, argument: string): NoulAnswer {
	const dangerous = /rm\s+-rf|Remove-Item|format\s+disk|curl.+\|.+sh|\.env|\.ssh|node_modules/i.test(argument);
	return { noul: dangerous ? 0.02 : 0.96 };
}

async function askJev(state: unknown, questions: Record<string, unknown>): Promise<JevResponse> {
	const key = process.env.TYPESAFE_API_KEY;
	if (!key) {
		const record = state as Record<string, unknown>;
		return {
			model: "offline-simulation",
			answers: {
				...("tool" in record
					? { allowed: offlineGate(String(record.tool), String(record.argument)) }
					: { skill: offlineChoice(String(record.task)) }),
			},
		};
	}

	const response = await fetch("https://api.typesafe.ai/v1/systemone", {
		method: "POST",
		headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
		body: JSON.stringify({ model: "jev-latest", state, questions }),
	});
	if (!response.ok) throw new Error(`Jev HTTP ${response.status}`);
	return (await response.json()) as JevResponse;
}

function emit(ctx: ExtensionContext, payload: Record<string, unknown>, level: "info" | "warning" = "info") {
	ctx.ui.notify(PREFIX + JSON.stringify(payload), level);
}

export default function piJevDemo(pi: ExtensionAPI) {
	let selectedSkill: { name: string; content: string } | undefined;

	pi.on("before_agent_start", (event) => {
		if (!selectedSkill) return;
		return {
			message: {
				customType: "pi-jev-demo-skill",
				content: `<selected-skill name="${selectedSkill.name}">\n${selectedSkill.content}\n</selected-skill>`,
				display: true,
			},
		};
	});

	pi.registerCommand("jev-demo-skill", {
		description: "用 Jev 选择一个 Skill：/jev-demo-skill <任务>",
		handler: async (args, ctx) => {
			const task = args.trim();
			if (!task) {
				emit(ctx, { error: "请提供任务文本" }, "warning");
				return;
			}
			const state = { task, available_skills: SKILLS };
			const questions = {
				skill: {
					type: "choice",
					instructions: "当前任务最应该加载哪个 Skill？",
					criteria: SKILLS,
				},
			};
			try {
				const result = await askJev(state, questions);
				const answer = result.answers.skill as ChoiceAnswer;
				const loadedSkill = loadSkill(answer.choice);
				selectedSkill = { name: answer.choice, content: loadedSkill };
				emit(ctx, {
					kind: "pick_skill",
					state,
					jev: answer,
					branch: `load skill: ${answer.choice}`,
					loaded_skill_preview: loadedSkill.slice(0, 240),
					model: result.model,
				});
			} catch (error) {
				emit(ctx, { kind: "pick_skill", error: String(error), branch: "keep current skill and ask the main agent" }, "warning");
			}
		},
	});

	pi.registerCommand("jev-demo-gate", {
		description: "用 Jev 判断工具调用是否放行：/jev-demo-gate <tool> <argument>",
		handler: async (args, ctx) => {
			const [tool = "bash", ...rest] = args.trim().split(/\s+/);
			const argument = rest.join(" ");
			const state = { tool, argument, task: "只允许安全的项目内操作" };
			const questions = {
				allowed: {
					type: "noul",
					instructions: "这个工具调用可以在无需人工确认的情况下执行吗？",
					criteria: { true: "只读或项目内低风险操作", false: "破坏性、越界或明显危险操作" },
				},
			};
			try {
				const result = await askJev(state, questions);
				const answer = result.answers.allowed as NoulAnswer;
				const branch = answer.noul >= 0.8 ? "allow" : answer.noul <= 0.2 ? "block" : "ask_user";
				emit(ctx, { kind: "gate", state, jev: answer, branch, model: result.model }, branch === "block" ? "warning" : "info");
			} catch (error) {
				emit(ctx, { kind: "gate", error: String(error), branch: "ask_user" }, "warning");
			}
		},
	});

	pi.on("tool_call", async (event, ctx) => {
		if (event.toolName !== "bash" && event.toolName !== "write" && event.toolName !== "edit") return;
		const input = JSON.stringify(event.input);
		try {
			const result = await askJev({ tool: event.toolName, argument: input, task: "保护工作区" }, {
				allowed: { type: "noul", instructions: "这个工具调用可以安全执行吗？" },
			});
			const answer = result.answers.allowed as NoulAnswer;
			if (answer.noul < 0.2) return { block: true, reason: "Jev gate blocked this tool call" };
		} catch {
			// Fail closed for the real tool hook; the teaching command reports the fallback explicitly.
			return { block: true, reason: "Jev gate unavailable; manual confirmation required" };
		}
	});
}
