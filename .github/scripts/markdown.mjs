// Markdown helpers for the label job summaries. Every value that comes from
// the manifest or the GitHub API passes through one of them, so a backtick,
// pipe or line break in a label name, colour or error cannot change the
// structure of the summary.

// One line: CR, LF and CRLF become spaces.
export function singleLine(value) {
  return String(value).replace(/\r\n?|\n/g, " ");
}

// Plain text, on one line, with pipes escaped for table cells.
export function markdownEscape(value) {
  return singleLine(value).replaceAll("|", "\\|");
}

// A code span the value cannot close: its delimiter is one backtick longer
// than the longest run of backticks in the value. Inside a table, pipes are
// escaped as well.
export function inlineCode(value, { table = false } = {}) {
  let text = singleLine(value);
  if (table) text = text.replaceAll("|", "\\|");
  const longest = Math.max(0, ...(text.match(/`+/g) ?? []).map(run => run.length));
  const fence = "`".repeat(longest + 1);
  const padding = /^[` ]|[` ]$/.test(text) ? " " : "";
  return `${fence}${padding}${text}${padding}${fence}`;
}
