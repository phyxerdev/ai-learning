"""
Day 8 - Tool use: your first AI agent
Run (in the same folder as llm.py and .env):
    python day8_agent.py

The model cannot run code, check websites or know the time by itself.
We DESCRIBE tools to it. When it wants one, it replies with a "tool call";
our Python runs the real function and sends the result back.
That loop = an agent.
"""
import ast
import json
import operator
import socket
import urllib.request
from datetime import datetime

from llm import client, MODEL, NO_THINK_TAG

MAX_STEPS = 6          # safety: stop if the agent loops too long
SHOW_STEPS = True      # print every tool call so you can watch the agent think


# =====================================================================
# 1. The REAL functions (plain Python - the model never sees this code)
# =====================================================================
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg}


def calculator(expression: str) -> str:
    """Safely evaluate maths like '2400 * 0.15'. (Never use eval() on model output!)"""
    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_eval(node.operand))
        raise ValueError("only numbers and + - * / ** % are allowed")
    try:
        return str(round(_eval(ast.parse(expression, mode="eval").body), 6))
    except Exception as e:
        return f"error: {e}"


def check_domain(domain: str) -> str:
    """
    Basic reachability check: does DNS resolve, and does the site answer?
    >>> Replace the body with the check from your Nawala bot <<<
    (e.g. compare the resolved IP against Nawala's block-page IPs).
    """
    domain = domain.replace("https://", "").replace("http://", "").strip("/")
    result = {"domain": domain}
    try:
        result["ip"] = socket.gethostbyname(domain)
    except socket.gaierror:
        result["status"] = "DNS does not resolve (blocked or does not exist)"
        return json.dumps(result)
    try:
        req = urllib.request.Request(f"https://{domain}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            result["http_status"] = r.status
            result["status"] = "reachable"
    except Exception as e:
        result["status"] = f"DNS ok but site not reachable: {type(e).__name__}"
    return json.dumps(result)


def get_current_time() -> str:
    """The model has no clock - this gives it one."""
    return datetime.now().strftime("%A %d %B %Y, %H:%M")


# Map tool names -> real functions
TOOL_FUNCTIONS = {
    "calculator": calculator,
    "check_domain": check_domain,
    "get_current_time": get_current_time,
}


# =====================================================================
# 2. The tool DESCRIPTIONS (this is all the model sees)
#    Good descriptions = the model picks the right tool at the right time.
# =====================================================================
TOOLS = [
    {"type": "function", "function": {
        "name": "calculator",
        "description": "Evaluate a maths expression. Use for ANY arithmetic, percentages, CTR, CPA etc. "
                       "Example: '2400 * 15 / 100'.",
        "parameters": {"type": "object",
                       "properties": {"expression": {"type": "string", "description": "e.g. '120 / 18'"}},
                       "required": ["expression"]}}},
    {"type": "function", "function": {
        "name": "check_domain",
        "description": "Check whether a website domain resolves and is reachable (possible blocking).",
        "parameters": {"type": "object",
                       "properties": {"domain": {"type": "string", "description": "e.g. 'example.com'"}},
                       "required": ["domain"]}}},
    {"type": "function", "function": {
        "name": "get_current_time",
        "description": "Get the current local date and time.",
        "parameters": {"type": "object", "properties": {}}}},
]

SYSTEM_PROMPT = """You are a helpful assistant with tools.
- For any arithmetic, ALWAYS use the calculator tool. Never do maths in your head.
- For questions about whether a website works or is blocked, use check_domain.
- For today's date or time, use get_current_time.
- After getting tool results, answer the user briefly and clearly."""


# =====================================================================
# 3. The AGENT LOOP
# =====================================================================
def run_agent(user_question, history):
    history.append({"role": "user", "content": user_question + NO_THINK_TAG})

    for step in range(1, MAX_STEPS + 1):
        resp = client.chat.completions.create(model=MODEL, messages=history, tools=TOOLS, temperature=0)
        msg = resp.choices[0].message

        # No tool calls -> the model is giving its final answer
        if not msg.tool_calls:
            history.append({"role": "assistant", "content": msg.content or ""})
            return msg.content

        # The model wants tools. Record its request in the history first...
        history.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [{"id": tc.id, "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                           for tc in msg.tool_calls],
        })

        # ...then run each tool and send back the result
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            func = TOOL_FUNCTIONS.get(name)
            result = func(**args) if func else f"error: unknown tool '{name}'"

            if SHOW_STEPS:
                print(f"  [step {step}] {name}({args}) -> {result}")

            history.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})

    return "(stopped: too many steps - the agent may be stuck in a loop)"


def main():
    print(f"Agent running on {MODEL}. Type /quit to exit, /reset to clear memory.")
    print("Try: Is example.com reachable, and what is 15% of 2,400?\n")
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    while True:
        q = input("You: ").strip()
        if not q:
            continue
        if q == "/quit":
            break
        if q == "/reset":
            history = history[:1]
            print("(memory cleared)\n")
            continue
        try:
            answer = run_agent(q, history)
        except Exception as e:
            answer = f"(error: {e})"
        print(f"Agent: {answer}\n")


if __name__ == "__main__":
    main()