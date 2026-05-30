import os
import anthropic
from dotenv import load_dotenv
from server import list_tables, get_schema, run_query

load_dotenv()

MODEL = "claude-sonnet-4-5"



def build_schema_context() -> str:
    tables = list_tables()
    if tables.startswith("No tables"):
        return "No tables available."
    parts = []
    for table in tables.splitlines():
        table = table.strip()
        if table:
            parts.append(f"Table: {table}\n{get_schema(table)}")
    return "\n\n".join(parts)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences if the model wraps the SQL in them."""
    if "```" not in text:
        return text
    return "\n".join(
        line for line in text.splitlines() if not line.startswith("```")
    ).strip()


def ask_nba(client: anthropic.Anthropic, question: str, schema_context: str) -> str:
    # Step 1: Generate SQL from the question + schema
    sql_resp = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=[
            {
                "type": "text",
                "text": (
                    "You are a PostgreSQL expert. Using the database schema below, write "
                    "a single read-only SELECT query that answers the user's question. "
                    "Respond with ONLY the raw SQL — no explanation, no markdown fences.\n\n"
                    f"Schema:\n{schema_context}"
                ),
                # Cache the stable schema so repeated questions pay only for the question tokens
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": question}],
    )
    sql = _strip_fences(sql_resp.content[0].text.strip())

    # Step 2: Execute the query
    results = run_query(sql)

    # Step 3: Turn the raw results into a natural language answer
    answer_resp = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=(
            "You are a helpful NBA stats assistant. "
            "Answer questions naturally and concisely based on the query results provided. "
            "Do not mention SQL or technical details unless asked."
        ),
        messages=[
            {
                "role": "user",
                "content": f"Question: {question}\n\nQuery results:\n{results}",
            }
        ],
    )
    return answer_resp.content[0].text.strip()


def main() -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")

    client = anthropic.Anthropic(api_key=api_key)

    print("Loading database schema...")
    schema_context = build_schema_context()
    print("Ask-Me-Anything-Assistant ready (type 'quit' to exit).\n")

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            break
        try:
            answer = ask_nba(client, question, schema_context)
            print(f"\nAssistant: {answer}\n")
        except Exception as exc:
            print(f"\nError: {exc}\n")


if __name__ == "__main__":
    main()
