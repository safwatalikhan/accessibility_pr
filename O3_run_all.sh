#!/bin/bash

TOTAL_START=$(date +%s%3N)
CMD_NUM=0
TOTAL_CMDS=150

run_cmd() {
    CMD_NUM=$((CMD_NUM + 1))
    local CMD="$*"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  [$CMD_NUM/$TOTAL_CMDS] Running: $CMD"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    local START=$(date +%s%3N)

    eval "$CMD"
    local EXIT_CODE=$?

    local END=$(date +%s%3N)
    local ELAPSED=$(echo "scale=2; ($END - $START) / 1000" | bc)
    echo ""
    echo "  Total elapsed time: ${ELAPSED} seconds  (exit code: $EXIT_CODE)"

    if [ $EXIT_CODE -ne 0 ]; then
        echo "  ⚠️  Command exited with non-zero status: $EXIT_CODE"
    fi
}

run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_909833569 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_909833569 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_909833569 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_918881766 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_918881766 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_918881766 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_946583554 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_946583554 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_946583554 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_950782151 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_950782151 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cds-snc_digital-canada-ca/issues/PR_950782151 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cylc_cylc-ui/issues/PR_579637170 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cylc_cylc-ui/issues/PR_579637170 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/cylc_cylc-ui/issues/PR_579637170 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dddeastmidlandslimited_dddem-web/issues/PR_503646332 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dddeastmidlandslimited_dddem-web/issues/PR_503646332 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dddeastmidlandslimited_dddem-web/issues/PR_503646332 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dequelabs_cauldron/issues/PR_1584879360 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dequelabs_cauldron/issues/PR_1584879360 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dequelabs_cauldron/issues/PR_1584879360 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2127762492 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2127762492 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2127762492 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2173547118 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2173547118 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2173547118 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2207657543 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2207657543 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2207657543 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2214849521 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2214849521 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2214849521 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2385490709 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2385490709 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/dhis2_ui/issues/PR_2385490709 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/gympass_yoga/issues/PR_2756476017 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/gympass_yoga/issues/PR_2756476017 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/gympass_yoga/issues/PR_2756476017 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/gympass_yoga/issues/PR_2921068887 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/gympass_yoga/issues/PR_2921068887 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/gympass_yoga/issues/PR_2921068887 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/inclusive-design_wecount.inclusivedesign.ca/issues/PR_2179910857 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/inclusive-design_wecount.inclusivedesign.ca/issues/PR_2179910857 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/inclusive-design_wecount.inclusivedesign.ca/issues/PR_2179910857 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1102620289 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1102620289 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1102620289 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1134423997 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1134423997 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1134423997 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1213690009 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1213690009 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_1213690009 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_3019067117 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_3019067117 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/leaflet_leaflet/issues/PR_3019067117 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_321971039 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_321971039 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_321971039 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_321982888 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_321982888 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_321982888 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_328812522 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_328812522 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/maplibre_maputnik/issues/PR_328812522 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/mdo_github-buttons/issues/PR_610713911 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/mdo_github-buttons/issues/PR_610713911 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/mdo_github-buttons/issues/PR_610713911 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/mdo_github-buttons/issues/PR_65070942 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/mdo_github-buttons/issues/PR_65070942 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/mdo_github-buttons/issues/PR_65070942 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1154179361 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1154179361 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1154179361 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1335734686 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1335734686 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1335734686 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1336005533 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1336005533 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1336005533 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1348102534 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1348102534 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1348102534 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1701725770 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1701725770 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1701725770 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1845281685 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1845281685 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_1845281685 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_3068230238 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_3068230238 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_3068230238 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_500942454 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_500942454 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_500942454 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_795221767 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_795221767 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_795221767 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_798401620 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_798401620 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_798401620 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_802213497 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_802213497 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/onsdigital_design-system/issues/PR_802213497 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1061148272 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1061148272 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1061148272 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1129640638 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1129640638 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1129640638 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1163893375 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1163893375 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1163893375 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1821851175 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1821851175 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/refinitiv_refinitiv-ui/issues/PR_1821851175 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_1029860470 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_1029860470 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_1029860470 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_1515922121 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_1515922121 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_1515922121 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_254146241 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_254146241 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_254146241 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_580066898 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_580066898 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_580066898 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_613653257 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_613653257 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_613653257 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_714819179 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_714819179 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_714819179 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_915924080 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_915924080 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/twbs_bootstrap/issues/PR_915924080 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/unl_wdntemplates/issues/PR_231402510 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/unl_wdntemplates/issues/PR_231402510 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/unl_wdntemplates/issues/PR_231402510 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/unl_wdntemplates/issues/PR_461626704 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/unl_wdntemplates/issues/PR_461626704 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/unl_wdntemplates/issues/PR_461626704 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/unl_wdntemplates/issues/PR_891146471 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/unl_wdntemplates/issues/PR_891146471 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/unl_wdntemplates/issues/PR_891146471 --model qwen
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/zooniverse_front-end-monorepo/issues/PR_2164246828 --model claude
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/zooniverse_front-end-monorepo/issues/PR_2164246828 --model codex
run_cmd python3 O3_Script_agentic_ais.py --pr repair-benchmark/apps/zooniverse_front-end-monorepo/issues/PR_2164246828 --model qwen

TOTAL_END=$(date +%s%3N)
TOTAL_ELAPSED=$(echo "scale=2; ($TOTAL_END - $TOTAL_START) / 1000" | bc)
echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "  ✅ All $TOTAL_CMDS commands completed."
echo "  Total elapsed time: ${TOTAL_ELAPSED} seconds"
echo "════════════════════════════════════════════════════════════════════"
