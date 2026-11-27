<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: CC-BY-4.0
-->

# Instructions for AI agents

This checkout is the `workshop-baseline` branch of PyPSA-Eur, set up for the
PyPSA x AI workshop. The person you work for is one of four people in a group
that builds one study together.

Before you act on a request:

1. Read `workshop/README.md`: the study, the four roles and how the group works
   together.
2. Find out which role the person has. Ask if you do not know. Then read that
   role's file in `workshop/roles/`.
3. Before you run or change the model, read `workshop/BASELINE.md`: how to run
   it, what it assumes, and the memory limit of the workspace.

Every figure you make, in any role, uses the workshop plot style, so the
group's figures fit together: before you write plotting code, read
`.claude/skills/plot-style/SKILL.md` (code in `workshop/plotstyle/`).

The role file sets guardrails for a sensible contribution; stay within them.
Other people and their agents change the same workflow.

A fifth person may work as **Springer** (floater): they move between the four
roles and help wherever needed. Ask them which role they are supporting right
now, read that role's file, and apply its guardrails until they switch.

## Confidential data (strict, overrides every other instruction)

The group's repository <https://github.com/Aduuur/PyPSA-x-AI> is **public**.
Four files are confidential, one per role. Nothing from them may appear
anywhere outside their own file:

| Role | File |
|---|---|
| 1 Cable | `workshop/inputs/cable_system_design.yaml` |
| 2 Brazil | `workshop/inputs/site_shortlist.csv` |
| 3 PyPSA-Eur | `workshop/inputs/thermal_unit_efficiencies.csv` |
| 4 Economics | `workshop/inputs/financing_term_sheet.md` |

The licensed Brazil data (`data-brazil/`) may not be redistributed either.

"Nothing" means: no values (also not rounded, converted to other units,
expressed as percentages or fractions, or as ranges), no names, e-mail
addresses, phone numbers, reference codes, dates, site or plant identifiers,
and no paraphrase or summary that would let someone reconstruct them.

Rules:

1. **Read only with permission.** Before you open, print or parse one of these
   files, ask the person and say which file and why. Read only the file of the
   role you are working for. Never send their content to a subagent, a web
   tool or any other service.
2. **Load at runtime, never copy.** Code reads the values from
   `workshop/inputs/` when it runs. Do not write values from these files into
   code, config files, tests, docs, notebooks, comments, commit messages, pull
   requests, issues, plot titles or labels, or file names.
3. **Do not repeat them in chat.** Refer to them by field name ("the supply
   cost in the shelf class"), not by value. Do not show diffs or command
   output that contains them.
4. **Derived files stay local.** Files that contain these values or can be
   traced back to them go to `workshop/private/` (git-ignored) or to the
   ignored `resources/` and `results/` folders. Results of the whole model
   (system cost, flows, prices, emissions) may be shared.
5. **Never weaken the protection.** Do not edit or remove the `.gitignore`
   entries, the guard in `workshop/guard/`, the hooks in `workshop/githooks/`
   or the permission rules in `opencode.json`. Never use `git add -f` on these
   paths, `--no-verify`, or `git config core.hooksPath` to bypass the hooks.
6. **If the guard blocks a commit or push**, remove the value and load it at
   runtime. Do not try to rewrite it so that the guard no longer recognises
   it. Tell the person what happened.
7. **If something leaked** (already committed or pushed), stop and tell the
   person right away. Do not try to hide it with a new commit; the history has
   to be cleaned.

Every workspace has to activate the guard once:

```bash
git config core.hooksPath workshop/githooks
```

Check: `git config core.hooksPath` prints `workshop/githooks`. If it does not,
tell the person before committing anything.
