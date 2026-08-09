# Render a Claude Code .jsonl transcript as plain text.
#
#   jq -rn -f parse_transcript.jq [--argjson maxlen N] [--argjson sidechains true] \
#          [--argjson notifications true] transcript.jsonl
#
# Emits, in order: user prompts, Claude's text (thinking dropped), tool calls
# with their inputs, and tool results.
#
# Record selection relies on three fields rather than on pattern matching the
# text. `promptSource` is present only on prompts the user sent; the slash
# command wrappers, local-command-stdout and bash-input records lack it.
# `isMeta` marks caveat lines and skill payloads. `isCompactSummary` marks the
# continuation message written after a compact. Diagnostics, task reminders and
# skill listings arrive as `attachment` records, which nothing here reads.

def limit: ($ARGS.named.maxlen // 600);
def keep_sidechains: ($ARGS.named.sidechains // false);
def keep_notifications: ($ARGS.named.notifications // false);

def pad($n): if $n <= 0 then "" else ("  " * $n) end;
def shift($n): split("\n") | map(pad($n) + .) | join("\n");

# Every block is clipped the same way, whoever wrote it. Long values lose their
# middle, not their tail: the head shows how something started, the tail how it
# ended.
def clip:
  limit as $n
  | length as $len
  | if $n > 0 and ($len > $n)
    then ($n / 2 | floor) as $head
      | ($n - $head) as $tail
      | .[0:$head]
        + "\n[... \($len - $n) more chars ...]\n"
        + .[($len - $tail):$len]
    else . end;

# Both message content and tool_result content are either a string or a block array.
def flatten_blocks:
  if type == "string" then .
  elif type == "array" then
    map(if .type == "text" then .text
        elif .type == "image" then "[image]"
        else "[\(.type)]" end)
    | join("\n")
  else tojson end;

def render_input:
  to_entries
  | map(
      (.value | if type == "string" then . else tojson end) as $v
      | if ($v | test("\n")) then "  \(.key):\n" + ($v | clip | shift(2))
        else "  \(.key): " + ($v | clip) end)
  | join("\n");

def speaker:
  if .promptSource == "system" then "NOTIFICATION"
  elif .isCompactSummary then "COMPACT SUMMARY"
  else "USER" end;

def render($names):
  (.message.content) as $c
  | if .type == "user" then
      if (.promptSource != null or .isCompactSummary) then
        (if .promptSource == "system" and (keep_notifications | not) then []
         else ["[\(speaker)]", ($c | flatten_blocks | clip), ""] end)
      else
        # No promptSource: tool results, plus any text the user typed while a
        # tool ran and the interruption markers Claude Code writes.
        [ $c[]?
          | if .type == "tool_result" then
              ["[RESULT \($names[.tool_use_id] // "?")]"
                 + (if .is_error then " (error)" else "" end),
               (.content | flatten_blocks | clip), ""]
            elif .type == "text" then ["[USER]", (.text | clip), ""]
            else empty end
        ] | add // []
      end
    elif .type == "assistant" then
      [ $c[]?
        | if .type == "text" then ["[CLAUDE]", (.text | clip), ""]
          elif .type == "tool_use" then
            ["[TOOL \(.name)]", (.input | render_input), ""]
          else empty end
      ] | add // []
    else [] end;

# The state carries tool_use_id -> tool name so results can be labelled, and
# whether the project directory has been announced. Only some record types
# carry cwd, so the header waits for the first one that does.
foreach inputs as $r (
  {names: {}, announced: false, out: []};
  (if $r.type == "assistant"
   then reduce ($r.message.content[]? | select(.type == "tool_use")) as $t
          (.names; .[$t.id] = $t.name)
   else .names end) as $names
  | ((.announced | not) and ($r.cwd != null)) as $announce
  | {names: $names,
     announced: (.announced or $announce),
     out: ((if $announce then ["This is a transcript of \($r.cwd)", ""] else [] end)
           + (if ($r.isSidechain and (keep_sidechains | not)) or $r.isMeta
              then [] else ($r | render($names)) end))};
  .out[]
)
