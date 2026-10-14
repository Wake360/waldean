# agent-protocol, 2026-10-14

Indicative only. Pre-registered arms, criteria and decision rule in `agent-protocol/MANIFEST.json`.

| arm | runs | notebook | valid (95% CI) | temporal fail | group fail | leak fail | selection fail | median abs gap (n) |
|---|---|---|---|---|---|---|---|---|
| A | 32 | 32 | 25/32 (61%-89%) | 2/16 | 1/8 | 0/16 | 4/32 | 0.025 (23) |
| B | 80 | 80 | 79/80 (93%-100%) | 1/40 | 0/20 | 0/40 | 0/80 | 0.033 (49) |
| C | 80 | 80 | 80/80 (95%-100%) | 0/40 | 0/20 | 0/40 | 0/80 | 0.023 (80) |

## Differences in failure rate

| comparison | difference | 95% CI (Newcombe) |
|---|---|---|
| A minus B | +21% | +8% to +38% |
| B minus C | +1% | -3% to +7% |

Primary: B minus C failure rate lower bound -3.4%, median gap B 0.033 vs C 0.023, completion B 100% vs C 100%: no evidence that C is better.

## Secondary analyses (amendment 1, registered before scoring)

1. Boschloo exact, two-sided, B 1/80 vs C 0/80: p = 0.8276.
2. Criteria not passed per run, Mann-Whitney two-sided: mean B 0.013 vs C 0.000, p = 0.3234.
3. Beta(1,1) posterior P(failure rate C < B) = 0.7486.
4. Mantel-Haenszel odds ratio of failure B vs C, stratified by dataset: undefined (an arm has no failures or no passes in every dataset); shipments B 0/20 C 0/20; tutoring B 0/20 C 0/20; meters B 1/20 C 0/20; warranty B 0/20 C 0/20.
5. Failure counts per criterion per arm: see the arm table above.

## Runs

| run | arm | cli | temporal | group | leak | selection | headline | future AUC | waldean check |
|---|---|---|---|---|---|---|---|---|---|
| meters-claude-A-0 | A | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.755) | 0.7287135115687888 | - |
| meters-claude-A-1 | A | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.764754693163337 | - |
| meters-claude-A-2 | A | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.731) | 0.7486616984626396 | - |
| meters-claude-A-3 | A | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7405503239745297) | 0.7669296339283238 | - |
| meters-claude-A-4 | A | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7130896800262434) | 0.713679116008802 | - |
| meters-claude-A-5 | A | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7439835625628983) | 0.768932404940751 | - |
| meters-claude-A-6 | A | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('roc_auc', 0.7514230124119423) | 0.7748399232628249 | - |
| meters-claude-A-7 | A | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7313823863368412) | 0.7281048258770316 | - |
| meters-claude-B-0 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7373386670066288) | 0.7642369303374935 | leakage-test-selection |
| meters-claude-B-1 | B | 2.1.296 (Claude Code) | fail | n/a | pass | pass | ('roc_auc', 0.7191399870582071) | 0.7688408944647601 | - |
| meters-claude-B-10 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7221777822217779) | 0.7570332225335772 | - |
| meters-claude-B-11 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('average_precision', 0.49491243756100783) | 0.7684208707817235 | - |
| meters-claude-B-12 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7429407048046471) | 0.7709433633202507 | - |
| meters-claude-B-13 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('average_precision', 0.4979236934048923) | 0.7685834429030257 | - |
| meters-claude-B-14 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('average_precision', 0.5088664647718112) | 0.7704026837014044 | - |
| meters-claude-B-15 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('average_precision', 0.4979236934048923) | 0.7685834429030257 | - |
| meters-claude-B-16 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('average_precision', 0.5265563603087406) | 0.7691137022365065 | - |
| meters-claude-B-17 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7442116739349212) | 0.7688800684698931 | - |
| meters-claude-B-18 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7191399870582071) | 0.7688408944647601 | - |
| meters-claude-B-19 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('average_precision', 0.47650599533754334) | 0.7643882203453172 | - |
| meters-claude-B-2 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7499167835963825) | 0.7671076797816536 | - |
| meters-claude-B-3 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7266144239389162) | 0.7672370323466028 | - |
| meters-claude-B-4 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7537805201797282) | 0.7653100630341083 | - |
| meters-claude-B-5 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7137222742892846) | 0.7745929703344661 | - |
| meters-claude-B-6 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('average_precision', 0.4965980883249848) | 0.7672370323466028 | - |
| meters-claude-B-7 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7286839715573871) | 0.7620755437782827 | - |
| meters-claude-B-8 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7445887170848414) | 0.7715630960814556 | - |
| meters-claude-B-9 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7312834224598932) | 0.7644307633148918 | - |
| meters-claude-C-0 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-1 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-10 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-11 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-12 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.741) | 0.768468976460027 | - |
| meters-claude-C-13 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-14 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-15 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-16 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-17 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-18 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-19 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-2 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-3 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-4 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.738) | 0.7653876275642717 | - |
| meters-claude-C-5 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-6 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-7 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-8 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| meters-claude-C-9 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.74) | 0.7670948307079698 | - |
| shipments-claude-A-0 | A | 2.1.296 (Claude Code) | fail | n/a | pass | pass | ('test_auc', 0.6818710635054358) | 0.7112803772216177 | - |
| shipments-claude-A-1 | A | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_auc', 0.686296003975562) | 0.7034820457018498 | - |
| shipments-claude-A-2 | A | 2.1.296 (Claude Code) | fail | n/a | pass | pass | ('test_auc', 0.606) | 0.7007254261878854 | - |
| shipments-claude-A-3 | A | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7103312982103113) | 0.6858179180268408 | - |
| shipments-claude-A-4 | A | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_auc', 0.594) | 0.708487486398259 | - |
| shipments-claude-A-5 | A | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('mean_rolling_logreg_auc', 0.7199636832379362) | 0.7207834602829163 | - |
| shipments-claude-A-6 | A | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_auc', 0.7617140683459609) | None | - |
| shipments-claude-A-7 | A | 2.1.296 (Claude Code) | pass | n/a | pass | fail | ('oof_roc_auc', 0.684) | 0.7275661951396446 | - |
| shipments-claude-B-0 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7036983321247281) | 0.7264780558578166 | - |
| shipments-claude-B-1 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7036983321247281) | 0.7264780558578166 | - |
| shipments-claude-B-10 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7035464852607709) | 0.7265868697859993 | - |
| shipments-claude-B-11 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7036983321247281) | 0.7264780558578166 | - |
| shipments-claude-B-12 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7036983321247281) | 0.7264780558578166 | - |
| shipments-claude-B-13 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7036983321247281) | 0.7264780558578166 | - |
| shipments-claude-B-14 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7036983321247281) | 0.7264780558578166 | - |
| shipments-claude-B-15 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7037164612037708) | 0.7266956837141823 | - |
| shipments-claude-B-16 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.680130529369108) | 0.7247188973521944 | - |
| shipments-claude-B-17 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7034557823129252) | 0.7265505984766051 | - |
| shipments-claude-B-18 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7036983321247281) | 0.7264780558578166 | - |
| shipments-claude-B-19 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7036983321247281) | 0.7264780558578166 | - |
| shipments-claude-B-2 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7036983321247281) | 0.7264780558578166 | - |
| shipments-claude-B-3 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7036983321247281) | 0.7264780558578166 | - |
| shipments-claude-B-4 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.680130529369108) | 0.7247188973521944 | - |
| shipments-claude-B-5 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7036983321247281) | 0.7264780558578166 | - |
| shipments-claude-B-6 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.6818981145757795) | 0.7256982227058397 | - |
| shipments-claude-B-7 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7037164612037708) | 0.7266956837141823 | - |
| shipments-claude-B-8 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.6833393763596809) | 0.7265687341313022 | - |
| shipments-claude-B-9 | B | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('test_roc_auc', 0.7036983321247281) | 0.7264780558578166 | - |
| shipments-claude-C-0 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7031292517006803) | 0.7263329706202395 | - |
| shipments-claude-C-1 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7031292517006803) | 0.7263329706202395 | - |
| shipments-claude-C-10 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.6705215419501134) | 0.7191149800507799 | - |
| shipments-claude-C-11 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7031292517006803) | 0.7263329706202395 | - |
| shipments-claude-C-12 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7031292517006803) | 0.7263329706202395 | - |
| shipments-claude-C-13 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.6670657596371882) | 0.713347841857091 | - |
| shipments-claude-C-14 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.6705215419501134) | 0.7191149800507799 | - |
| shipments-claude-C-15 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7031292517006803) | 0.7263329706202395 | - |
| shipments-claude-C-16 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7031292517006803) | 0.7263329706202395 | - |
| shipments-claude-C-17 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.6705215419501134) | 0.7191149800507799 | - |
| shipments-claude-C-18 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.6670113378684808) | 0.7132752992383025 | - |
| shipments-claude-C-19 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.6670657596371882) | 0.713347841857091 | - |
| shipments-claude-C-2 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7031292517006803) | 0.7263329706202395 | - |
| shipments-claude-C-3 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7031292517006803) | 0.7263329706202395 | - |
| shipments-claude-C-4 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.6676825396825397) | 0.714145810663765 | - |
| shipments-claude-C-5 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7031292517006803) | 0.7263329706202395 | - |
| shipments-claude-C-6 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.6705215419501134) | 0.7191149800507799 | - |
| shipments-claude-C-7 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7031292517006803) | 0.7263329706202395 | - |
| shipments-claude-C-8 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7031292517006803) | 0.7263329706202395 | - |
| shipments-claude-C-9 | C | 2.1.296 (Claude Code) | pass | n/a | pass | pass | ('roc_auc', 0.7031292517006803) | 0.7263329706202395 | - |
| tutoring-claude-A-0 | A | 2.1.296 (Claude Code) | n/a | pass | n/a | fail | ('roc_auc', 0.6001) | 0.5761733737177769 | - |
| tutoring-claude-A-1 | A | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5995) | 0.5741946922884176 | - |
| tutoring-claude-A-2 | A | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5849) | 0.5571096988604143 | - |
| tutoring-claude-A-3 | A | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.601) | 0.5761733737177769 | - |
| tutoring-claude-A-4 | A | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.6015) | None | - |
| tutoring-claude-A-5 | A | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.6004) | 0.5741946922884176 | - |
| tutoring-claude-A-6 | A | 2.1.296 (Claude Code) | n/a | fail | n/a | pass | ('roc_auc', 0.5995) | 0.5741946922884176 | - |
| tutoring-claude-A-7 | A | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5995) | 0.5741946922884176 | - |
| tutoring-claude-B-0 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5924) | 0.5761538360092667 | - |
| tutoring-claude-B-1 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5924) | 0.5761538360092667 | - |
| tutoring-claude-B-10 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5924) | 0.5761538360092667 | - |
| tutoring-claude-B-11 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5924) | 0.5761538360092667 | - |
| tutoring-claude-B-12 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5946) | 0.5752316561675905 | - |
| tutoring-claude-B-13 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5946) | 0.5750694931869569 | - |
| tutoring-claude-B-14 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5924) | 0.5761538360092667 | - |
| tutoring-claude-B-15 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5978) | 0.5371228672759502 | - |
| tutoring-claude-B-16 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5924) | 0.5761538360092667 | - |
| tutoring-claude-B-17 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5994) | 0.5665603326881006 | - |
| tutoring-claude-B-18 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5924) | 0.5761538360092667 | - |
| tutoring-claude-B-19 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5924) | 0.5761538360092667 | - |
| tutoring-claude-B-2 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5504) | 0.5340217444926862 | - |
| tutoring-claude-B-3 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5924) | 0.5761528591238412 | - |
| tutoring-claude-B-4 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5946) | 0.5750694931869569 | - |
| tutoring-claude-B-5 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5946) | 0.5750694931869569 | - |
| tutoring-claude-B-6 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5994) | 0.5665603326881006 | - |
| tutoring-claude-B-7 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5924) | 0.5761572551082561 | - |
| tutoring-claude-B-8 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5924) | 0.5761538360092667 | - |
| tutoring-claude-B-9 | B | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.5946) | 0.5750694931869569 | - |
| tutoring-claude-C-0 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.591) | 0.5734840081413631 | - |
| tutoring-claude-C-1 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.549) | 0.5318970186922142 | - |
| tutoring-claude-C-10 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.549) | 0.5318970186922142 | - |
| tutoring-claude-C-11 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.548) | 0.5042936556664483 | - |
| tutoring-claude-C-12 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.549) | 0.5313939226980794 | - |
| tutoring-claude-C-13 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.581) | 0.547942117584768 | - |
| tutoring-claude-C-14 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.591) | 0.5734840081413631 | - |
| tutoring-claude-C-15 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.549) | 0.5313939226980794 | - |
| tutoring-claude-C-16 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.523) | 0.47418848906596567 | - |
| tutoring-claude-C-17 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.591) | 0.5734786352715229 | - |
| tutoring-claude-C-18 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.591) | 0.5734840081413631 | - |
| tutoring-claude-C-19 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.549) | 0.5318970186922142 | - |
| tutoring-claude-C-2 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.549) | 0.5318970186922142 | - |
| tutoring-claude-C-3 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.549) | 0.5318970186922142 | - |
| tutoring-claude-C-4 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.548) | 0.5042936556664483 | - |
| tutoring-claude-C-5 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.584) | 0.544680541370365 | - |
| tutoring-claude-C-6 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.53) | 0.4659540775930324 | - |
| tutoring-claude-C-7 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.592) | 0.573060528309407 | - |
| tutoring-claude-C-8 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.523) | 0.47418848906596567 | - |
| tutoring-claude-C-9 | C | 2.1.296 (Claude Code) | n/a | pass | n/a | pass | ('roc_auc', 0.591) | 0.5734840081413631 | - |
| warranty-claude-A-0 | A | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.7401) | 0.7134005094794119 | - |
| warranty-claude-A-1 | A | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.7283) | 0.7200934892411159 | - |
| warranty-claude-A-2 | A | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.7247) | 0.7201165844093758 | - |
| warranty-claude-A-3 | A | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.7401) | 0.7133312239746321 | - |
| warranty-claude-A-4 | A | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7135829613086646 | - |
| warranty-claude-A-5 | A | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.763) | 0.7192897773856732 | - |
| warranty-claude-A-6 | A | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.727) | 0.7190634447367266 | - |
| warranty-claude-A-7 | A | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7135829613086646 | - |
| warranty-claude-B-0 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7137815797556993 | - |
| warranty-claude-B-1 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7135829613086646 | - |
| warranty-claude-B-10 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7137815797556993 | leakage-test-selection |
| warranty-claude-B-11 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7137815797556993 | leakage-test-selection |
| warranty-claude-B-12 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7137815797556993 | - |
| warranty-claude-B-13 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('average_precision', 0.3416) | 0.7138116034744371 | - |
| warranty-claude-B-14 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7137815797556993 | - |
| warranty-claude-B-15 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7137815797556993 | - |
| warranty-claude-B-16 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7137815797556993 | - |
| warranty-claude-B-17 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7137815797556993 | - |
| warranty-claude-B-18 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('average_precision', 0.3321) | 0.7019949606342857 | - |
| warranty-claude-B-19 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7137815797556993 | - |
| warranty-claude-B-2 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7137815797556993 | - |
| warranty-claude-B-3 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.7611) | 0.7138116034744371 | - |
| warranty-claude-B-4 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('average_precision', 0.3432) | 0.7137815797556993 | - |
| warranty-claude-B-5 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('average_precision', 0.3433) | 0.7137885083061772 | - |
| warranty-claude-B-6 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7135829613086646 | - |
| warranty-claude-B-7 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.7611) | 0.7138116034744371 | - |
| warranty-claude-B-8 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7137815797556993 | - |
| warranty-claude-B-9 | B | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.761) | 0.7137815797556993 | - |
| warranty-claude-C-0 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-1 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6926266715740399) | 0.7132550099193747 | - |
| warranty-claude-C-10 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-11 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-12 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-13 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-14 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-15 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-16 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-17 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-18 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-19 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-2 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-3 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6926266715740399) | 0.7132550099193747 | - |
| warranty-claude-C-4 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-5 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-6 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-7 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-8 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |
| warranty-claude-C-9 | C | 2.1.296 (Claude Code) | n/a | n/a | n/a | pass | ('roc_auc', 0.6927248190406087) | 0.7133520096260662 | - |

## Prompt

`Here is data.csv and its data dictionary columns.csv. I want to know whether we can predict {question}. Build a notebook and save it as experiment.ipynb.`

Arm B appends ` Follow the methodology checklist in checklist.md. You can run `waldean check experiment.ipynb` to lint the notebook for statistical flaws.`.
Arm C appends ` Follow the experiment protocol in protocol.yaml. It fixes the holdout rows (holdout.csv), the cross-validation scheme and how the model is chosen. After running the notebook, run `waldean protocol check experiment.ipynb --protocol protocol.yaml` and fix what it reports.`.

## Notes

- The tables above were generated before commit 9410939. Their gap column (B 0.033, n 49; A n 23) uses the old ROC AUC name match. The corrected values are given below. Failure counts, intervals and secondary analyses do not depend on it.
- Decision, applied step by step to the registered rule. Newcombe 95% lower bound of (B failure rate minus C failure rate) is -3.4% (B 1/80, C 0/80, difference +1.3%, upper bound +6.7%). The lower bound is not above 0, so `c_better` does not hold, whatever the other two conditions say. They would hold: median absolute gap C 0.023 (n 80) is not above B 0.023 (n 69) + 0.02, and completion is 100% in both arms. The upper bound is not below 0, so `c_worse` does not hold either. Result: `no_evidence`. Under the registered rule this means: do not build the protocol as a separate product layer; keep the linter and evidence.
- What the result rests on. Baseline B failed one criterion in one run (meters-claude-B-1, a TimeSeriesSplit that cuts inside a billing month). With B at 1/80, even C at 0/80, which is what happened, gives a lower bound of -3.4%, so no C result could have met `c_better` at this n. Arm A (no checklist) failed 7/32: selection in meters-A-0, meters-A-6, shipments-A-7 and tutoring-A-0, temporal in shipments-A-0 and shipments-A-2, group in tutoring-A-6. A minus B is +21% (+8% to +38%). The checklist (B) carries the measured improvement; the protocol (C) adds nothing measurable to failure rates on these datasets.
- Estimation gap (descriptive). The median absolute gap between the headline ROC AUC and the AUC of the same model on future rows is 0.023 in both B (n 69) and C (n 80), and 0.025 in A (n 30). The 11 B runs without a gap headline average precision. Post-hoc correction: the first scoring counted only headlines named exactly `roc_auc` or `auc`, which dropped 20 B shipments runs named `test_roc_auc` and 7 A runs (`test_auc`, `oof_roc_auc` and similar) and showed B at 0.033 (n 49). Commit 9410939 counts any ROC AUC name and keeps PR AUC out. The correction was made after seeing results; it cannot change the decision, which fails on the lower bound.
- 192 runs planned and 192 scored, A 32, B 80, C 80. Every run produced a notebook. No `unbound` or `unreviewed` rows. No usage limit occurred. All 80 C runs pass `waldean protocol check`, and their `protocol.yaml` and `holdout.csv` match `files_sha256` in the manifest (160/160 hashes).
- Excluded and rerun runs. The similarity scan found 10 pairs at 1.00, each within one dataset and arm. In each the later run had executed the earlier run's leftover builder script in `/private/tmp/claude-501`, because leftovers were moved aside before each batch, not before each run. The later runs were moved to `runs-protocol-excluded/` and rerun: meters C-2, C-7, C-8, C-12; warranty B-6, C-13; shipments B-4; tutoring B-14, B-17, C-2. The meters C-2 rerun copied the C-12 rerun the same way and was rerun once more. After that the highest pair is 0.65 (warranty C-15/C-5) and 0.61 (meters C-0/C-8). Both were read: their own scripts, alike because the protocol fixes the split and the evidence format. Reruns ran about an hour after the rest of their cell.
- Independence (deviation). Agents share `/private/tmp/claude-501`. Per the user's decision, the harness only records new entries there (`user_tmp_new`) and the session moved the listed entries aside before each batch. That was not enough: an agent reading of all 192 final messages found 69 runs that saw another run's files and 56 that executed one at least once (A 7, B 21, C 28), six of them a script from a C run. Every one of those runs reports that its final notebook came from its own scripts. Sensitivity without the 56: A 7/25, B 1/59, C 0/52, B minus C +1.7% (-5.3% to +9.0%), median gap B 0.026 (n 52), C 0.023 (n 52). The decision does not change. Per-run classification is in the session workspace, not in this repo.
- `shared_tmp`. 37 runs left entries in `/private/tmp/claude` (their builder scripts and build dirs). The harness moved them to the run's `.agent-tmp` after each run, so none reached a later run through that dir.
- One stray directory: tutoring-claude-A-2 wrote a build dir next to its own run dir. It was moved aside; the run itself is kept.
- Harness location (deviation). At 19:41 another session switched the main checkout to a different branch. The batches from warranty on ran from a worktree of this branch at the same commit (21042f4). The agents use their own installed wheel, so no run saw different code.
- Bindings were written by eight agents, one per dataset and arm group (A+B, C), each reading every notebook in full and running the binding with the probes in a scratch copy. Judgement calls: meters-A-0 and A-6 and shipments-A-7 fail selection (pick by test or out-of-fold rows behind the headline); shipments-A-2 fails temporal (it reports random-fold CV); tutoring-A-6 fails group (it reports returning-student random-fold evals as a result); warranty A selection was read as chosen on train rows. `PROBE_FUTURE_AUC` is None in shipments-A-6 and tutoring-A-4 (no headline model to reuse without refitting).
- Second rater and adjudication, per amendment 2. Two fresh agents without the key (80 notebooks each) ruled temporal, group and selection on the 160 redacted B and C notebooks, seeing only the criterion texts, the `PROBE_EVALS` and `PROBE_SELECTED_ON` definitions and the dataset's `columns.csv`. Agreement with the first rater (`agent_baseline.py kappa`): temporal 80/80, kappa 1.00, the only fail on both sides being meters-claude-B-1; group 40/40 and selection 160/160, kappa undefined because neither rater marked a fail; pooled 280/280, kappa 1.00. No disagreements, so no adjudication. With one fail in 280 rulings, this check says little about the raters' sensitivity. A first second-rater pass on selection only, made before the session noticed amendment 2, also passed all 160 and is superseded.
- Amendments. Amendments 1 (extension and secondary analyses) and 2 (second rater on every criterion) were committed at 20:12 and 20:26 on 2026-10-13, during the main runs and before any binding or scoring. The amendment 1 extension is triggered only by `no_evidence` with a Newcombe upper bound of at least 10%. The upper bound is 6.7%, so there is no second batch, and `no_evidence` is final. The secondary analyses above are reported as registered.
- `waldean check` flagged `leakage-test-selection` in three B notebooks that both raters passed. Detector accuracy is not an endpoint here.
- Scoring is deterministic: a second `score` run gave a byte-identical `results.tsv`.
- Limits: four synthetic datasets designed by the author of the protocol (frozen before the runs, but by the same person), one prompt per arm, one agent (Claude Sonnet via Claude Code 2.1.296), an unblinded first rater, and C had the extra duty of writing `evidence.json`. The shipments data dictionary does not say that `claim_paid_eur` is recorded after delivery; no run used it as a feature. Indicative only (`gate_evidence: false`). No claim about agents in general.
