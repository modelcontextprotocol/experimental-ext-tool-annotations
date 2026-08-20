# Priorities for the Next Specification Iteration

This is a non-binding summary of where the
[Tool Annotations Interest Group](https://modelcontextprotocol.io/community/interest-groups/tool-annotations)
believes its attention would be most useful next. Consistent with its charter,
the IG gathers use cases, evaluates proposals, and makes recommendations. It
does not set the MCP roadmap, make binding specification decisions, or own SDK
implementation; these priorities are intended to focus discussion and feedback.

## 1. Mature Existing Extension Work

Support maintainers and contributors in completing the
[planned transition of existing SEP proposals](./sep-disposition.md) into fully
fledged experimental extensions with SDK implementations. The IG should gather
use cases, coordinate review, and establish clear evidence that the community
wants and will use each extension.

## 2. Prepare Pre-flight Requests for Review

Bring the pre-flight request proposal,
[SEP-1862: Tool Resolution](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1862),
into the extension framework and validate it with implementations. The
[`io.modelcontextprotocol/tool-resolution`](../specification/draft/tool-resolution.mdx)
draft preserves the pre-flight use case while using negotiated extension
capabilities and per-tool `_meta`.

## 3. Separate Human and Agent Content Presentation

Explore how content intended for human formatting and display can be represented
separately from content intended for agents. The goal is to let clients provide
good human-facing experiences without compromising the structured content
agents need.
[PR #7 proposes the `io.modelcontextprotocol/display-templates` experimental extension](https://github.com/modelcontextprotocol/experimental-ext-tool-annotations/pull/7)
for this purpose, covering both call-side display templates and result-side
rendered text. This belongs in the chartered discussion of tool-response
annotations and human-in-the-loop requirements.

## 4. Evaluate Annotation Proposals

Maintain an inventory of proposed annotation SEPs, evaluate how they relate to
one another and to the extension work, and provide consolidated feedback to
their authors and reviewers. The charter's current discussion list includes
[SEP-1913](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1913),
[SEP-1984](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1984),
and
[SEP-2417](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2417);
the inventory should evolve as proposals are opened, revised, or closed.
