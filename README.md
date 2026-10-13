# a1171622

Personal workspace repository.

## Claude Code skills

The `.claude/skills/` folder holds project skills for [Claude Code](https://claude.com/claude-code).
When Claude Code works in this repository it loads every skill in that folder automatically.

The current set is the 27 skills from [mattpocock/skills](https://github.com/mattpocock/skills)
(upstream commit `49dd158`), covering planning, specs, TDD, debugging, code review and similar
workflows. Their license is in `.claude/skills/LICENSE-mattpocock-skills`.

To add your own skill, create `.claude/skills/<skill-name>/SKILL.md`.
