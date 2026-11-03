# a1171622

Personal workspace repository.

## Claude Code skills

The `.claude/skills/` folder holds project skills for [Claude Code](https://claude.com/claude-code).
When Claude Code works in this repository it loads every skill in that folder automatically.

The current set is the 27 skills from [mattpocock/skills](https://github.com/mattpocock/skills)
(upstream commit `49dd158`), covering planning, specs, TDD, debugging, code review and similar
workflows. Their license is in `.claude/skills/LICENSE-mattpocock-skills`.

### House skills (Home Assistant project)

Five skills for the home-automation project. They point at the handoff note `claude/HANDOFF.md` in Home Assistant
for the current state of the house.

| Skill | Use it to |
|---|---|
| `ha-safe-edit` | change any Home Assistant file or automation: read live, back up, patch with a hash guard, review, check config, reload, verify, log |
| `ha-history-calc` | pull HA history or long-term statistics and write an engineering calc with numbers and assumptions |
| `hub-dashboard-edit` | change the custom hub dashboard with before/after screenshots at phone, tablet and desktop sizes |
| `independent-review` | run the reviewer role as a fresh subagent before a change ships |
| `house-health-check` | check how the house ran over a week and write a short report |

These load automatically in Claude Code sessions that work in this repository. To use them everywhere else on
claude.ai, add them to your account under Settings > Capabilities > Skills (upload each skill folder).

To add your own skill, create `.claude/skills/<skill-name>/SKILL.md`.
