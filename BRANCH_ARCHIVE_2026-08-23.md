# Legacy branch archive — 2026-08-23

This archive was created immediately after the approved H01 baseline was merged into `main` and successfully deployed to `trelweb.fly.dev`.

- Approved production main at archive time: `f03dc132b8f020d580bd1732fc72658efb0764a3`
- Archive history anchor: `9219bb97f24670a4dbc6b1ed9af6edf425001247`
- The anchor uses the approved main tree and includes every legacy branch tip as a parent, preserving their Git histories without mixing their file contents into production.

| Legacy branch | Archived tip | Last commit |
|---|---|---|
| `codex/add-property-workspace` | `94dfe97b021df9f6c96c6e1a3080e58df22e60e3` | Connect advertiser submissions to staff review |
| `codex/fix-test-workflow-dependencies` | `9539c2a7bddf021d1e00d7e3de2393c4b908af45` | Fix frontend dependency setup for test deployment |
| `codex/fix-test-workflow-yaml` | `866323c7f465359b6fa226a4991f6ea08a0b3a83` | Correct YAML line breaks in test workflow |
| `codex/fly-single-test-machine` | `1d62f00cae60bd40c658720d236fa47d66f7f829` | Limit test deployment to one Fly machine |
| `codex/fly-test-environment` | `0d61ca924ce9a7edeecdea1bdb45d4ecbe24b6aa` | Document Fly test environment setup |
| `codex/h01-authoritative-fly-test` | `6c7faebd428d112d1ba6882f46c86f8ccfebb425` | Honor account-category routing for compatibility login |
| `codex/improve-market-evidence-data-quality` | `e0c97a894923eb841a89c8b581439a1fa1a7e659` | Improve Market Evidence extraction and display |
| `codex/p1-schema-apply-once` | `3e2908825e4ce456f8af1c5a16c8d45c5b1282ce` | Verify applied P1 schema and legacy baseline |
| `codex/p1-schema-compatibility-verification` | `a0c9f0161747e31c23b638a17ba92e65e7046388` | Expose read-only P1 verification mode |
| `codex/p2-integrated-property-migration` | `1a5fecf90a5963f353dce6373344667eda933233` | Build frontend without unavailable lockfile cache |
| `codex/p3-final-hardening` | `bcc3c412697a0a42191c2753192856a4af98eb9b` | Fix P3 market link validation CI |
| `codex/p3-integrated-property-write-path` | `645c63572fe490a68f7552f194b10e18e263b75e` | Retry P3 apply with verified-empty collection fallback |
| `codex/reapply-approved-market-evidence-improvements` | `f1335cbec532fef185712173d0e7aa07a211db29` | Reapply approved Market Evidence quality improvements |
| `codex/reapply-market-evidence-improvements-to-branch` | `4c86c3bc781509789912763a20c1f3f623b053a7` | Reapply Market Evidence enrichment improvements |
| `codex/restore-advertiser-workspace` | `709c99a4bf6de994b42b8bea276ead6e40a4d7e9` | Harden Fly test deployment instructions |
| `codex/review-property-data-aggregation-module` | `606a532f4f037083e8704438e613570fcf188c86` | Fix scraper discovery consistency |
| `conflict_170826_1613` | `a2fe834d5e6e8e176029cd83710f19bccea45e9e` | Merge pull request #7 from erichaiara10/codex/improve-market-evidence-data-quality |
| `conflict_180826_0731` | `31839baf052f5aa773dc8ef17d5b6ae6641f6691` | Auto-generated changes |
| `emergent-final-handover-2026-08-21` | `4dddec8a6a1324dabedae75088bdaf73d133d656` | Auto-generated changes |
| `feature/must-change-password-first-login` | `a7711024c46f808758e1de32dd0af22200ecbd23` | Wire Add Property navigation and review edit links |
| `feature/p1-integrated-schema-extension` | `6f2b46948cbf95bcf00d180bdda6028a2bfeb670` | Add protected P1 schema extension workflow |
| `fix/temporary-backup-document-count` | `7dfa4cff8e893856ff5c6291d86b85f31b0f6dca` | Count singular document in backup verification |
| `flyio-new-files` | `37f8f4a1ba141b617bc48fe6d7ca5174d752ee18` | New files from Fly.io Launch |
| `flyio-scale-from-ui` | `e607f47908df58f5d6dc752863251782f5d26d4a` | Update backend/fly.toml scaling configuration via flyio-scale-from-ui |
| `iter42-scraper-diagnostics` | `8b0196291f112e06575feb7fa72cf65f529b6eb1` | Merge pull request #10 from erichaiara10/codex/reapply-market-evidence-improvements-to-branch |
| `ops/temporary-readonly-mongodb-backup` | `10bb1f63c2c5a6a0c55e5c482986d818cbe93311` | Use password-only secret for temporary MongoDB backup |
| `railway/code-change-aFLbW7` | `67c75bf1f9acbbf6382199fad3d2a8b1e7a25fb9` | fix: correct requirements.txt path in backend Dockerfile |
