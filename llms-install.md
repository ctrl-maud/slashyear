# Installing the slashyear MCP server

slashyear is a hosted, read-only MCP server. There is nothing to clone, build or run locally, and
no API key.

- URL: `https://slashyear.com/mcp`
- Transport: Streamable HTTP (JSON responses)
- Auth: none

## Cline

Add this to Cline's `cline_mcp_settings.json` (VS Code extension:
`<VS Code user dir>/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`;
Cline CLI: `~/.cline/data/settings/cline_mcp_settings.json`):

```json
{
  "mcpServers": {
    "slashyear": {
      "type": "streamableHttp",
      "url": "https://slashyear.com/mcp",
      "disabled": false
    }
  }
}
```

## Other clients

Claude Code:

```
claude mcp add --transport http slashyear https://slashyear.com/mcp
```

Cursor, VS Code and most other clients take the same `url` in their `mcpServers` config.

## Check it works

Ask: "Who led France in 1950?" The server should call `get_leaders` and answer with names, each
cited to a Wikipedia revision.

## Tools

| Tool | What it does |
|---|---|
| `search_history` | full-text search across every dated entry and subject |
| `get_year` | everything recorded for one year |
| `get_day` | one calendar day across every year |
| `get_timeline` | one subject's record in date order |
| `get_country` | one country's record, century by century |
| `get_year_facts` | a year (1800-2025) in numbers: prices, leaders, No. 1 song |
| `get_leaders` | heads of state and government for a country and year, 1800-2025 |
| `get_number_one_song` | Billboard Hot 100 No. 1 on a date, 1958 onward |
| `convert_dollars` | inflation-adjust U.S. dollars with BLS CPI-U, 1913 onward |
| `list_countries` | countries with a record of their own |
| `list_subjects` | subjects with a timeline |

Every entry is quoted verbatim from a specific English Wikipedia revision and carries its revision
id. Reuse under CC BY-SA 4.0.
