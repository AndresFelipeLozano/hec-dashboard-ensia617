from __future__ import annotations

from pathlib import Path
import sys
import unittest

import plotly.graph_objects as go


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from dashboard.components.design import (  # noqa: E402
    COMPARISON_COLOR,
    CURRENT_COLOR,
    PALETTE,
    SPECIALTY_PALETTE,
    TOKENS,
    apply_plotly_theme,
)
from dashboard.components.charts import (  # noqa: E402
    CHART_SELECTION_CONTRACT,
    MAX_CHART_HEIGHT,
    MIN_CHART_HEIGHT,
    PLOTLY_CONFIG,
    build_100pct_stacked_figure,
    build_dumbbell_figure,
    build_grouped_two_period_bar_figure,
    build_horizontal_category_bar_figure,
    build_lollipop_figure,
)


class VisualDesignTests(unittest.TestCase):
    def test_shared_tokens_match_the_approved_visual_reference(self):
        self.assertEqual(TOKENS["page"], "#F4F6F8")
        self.assertEqual(TOKENS["teal_900"], "#0F3D3E")
        self.assertEqual(TOKENS["teal_700"], "#146356")
        self.assertEqual(TOKENS["teal_500"], "#1A8F8C")
        self.assertEqual(TOKENS["text"], "#1C2B2C")
        self.assertEqual(TOKENS["muted"], "#5F7274")
        self.assertEqual(PALETTE[0], TOKENS["teal_500"])

    def test_shared_plotly_theme_is_neutral_and_readable(self):
        figure = apply_plotly_theme(go.Figure(go.Bar(x=["A"], y=[1])))
        self.assertEqual(figure.layout.paper_bgcolor, "rgba(0,0,0,0)")
        self.assertEqual(figure.layout.plot_bgcolor, "rgba(0,0,0,0)")
        self.assertEqual(figure.layout.font.color, TOKENS["text"])
        self.assertEqual(tuple(figure.layout.colorway), tuple(PALETTE))

    def test_chart_selection_contract_matches_analytical_question(self):
        self.assertEqual(CHART_SELECTION_CONTRACT["quantitative_relationship"], "bubble")
        self.assertEqual(CHART_SELECTION_CONTRACT["two_period_comparison"], "dumbbell")
        self.assertEqual(
            CHART_SELECTION_CONTRACT["series_two_period_comparison"],
            "horizontal_grouped_bar",
        )
        self.assertEqual(
            CHART_SELECTION_CONTRACT["mutually_exclusive_composition"],
            "horizontal_100pct_stacked",
        )
        self.assertEqual(
            CHART_SELECTION_CONTRACT["long_category_labels"],
            "horizontal_lollipop",
        )

    def test_two_period_chart_uses_governed_colors_labels_and_direct_delta(self):
        rows = [
            {
                "Indicador con nombre completo": "Etiqueta clínica completa",
                "Comparación": 90,
                "Actual": 104,
            }
        ]
        figure = build_dumbbell_figure(
            rows,
            label_key="Indicador con nombre completo",
            comparison_key="Comparación",
            current_key="Actual",
            axis_title="Episodios",
        )
        self.assertEqual(figure.data[0].marker.color, COMPARISON_COLOR)
        self.assertEqual(figure.data[1].marker.color, CURRENT_COLOR)
        self.assertIn("Δ +14", figure.data[1].text[0])
        self.assertEqual(figure.layout.yaxis.ticktext[0], "Etiqueta clínica completa")
        self.assertGreaterEqual(figure.layout.height, MIN_CHART_HEIGHT)
        self.assertLessEqual(figure.layout.height, MAX_CHART_HEIGHT)

    def test_lollipop_keeps_complete_labels_and_standard_height(self):
        label = "Prestación ambulatoria con un nombre clínico completo"
        figure = build_lollipop_figure(
            [{"Prestación": label, "Eventos": 17}],
            label_key="Prestación",
            value_key="Eventos",
            axis_title="Eventos",
        )
        self.assertEqual(figure.layout.yaxis.ticktext[0], label)
        self.assertGreaterEqual(figure.layout.height, MIN_CHART_HEIGHT)
        self.assertLessEqual(figure.layout.height, MAX_CHART_HEIGHT)

    def test_multi_series_two_period_bars_are_horizontal_and_slim(self):
        rows = [
            {"Período": period, "Serie": series, "Eventos": value}
            for period, values in (
                ("Comparación", (56, 50, 4)),
                ("Actual", (56, 48, 5)),
            )
            for series, value in zip(
                ("Programada", "Completada", "Inasistencia"), values
            )
        ]
        figure = build_grouped_two_period_bar_figure(
            rows,
            period_key="Período",
            series_key="Serie",
            value_key="Eventos",
            axis_title="Eventos",
        )
        self.assertEqual(len(figure.data), 2)
        self.assertTrue(all(trace.orientation == "h" for trace in figure.data))
        self.assertTrue(all(trace.width == 0.28 for trace in figure.data))
        self.assertEqual(figure.data[0].marker.color, COMPARISON_COLOR)
        self.assertEqual(figure.data[1].marker.color, CURRENT_COLOR)

    def test_specialty_bar_colors_are_distinct_without_redundant_legend(self):
        rows = [
            {"Especialidad": f"Especialidad {index}", "Eventos": 80 + index}
            for index in range(8)
        ]
        color_map = {
            row["Especialidad"]: SPECIALTY_PALETTE[index]
            for index, row in enumerate(rows)
        }
        figure = build_horizontal_category_bar_figure(
            rows,
            label_key="Especialidad",
            value_key="Eventos",
            axis_title="Eventos",
            color_map=color_map,
        )
        self.assertEqual(figure.data[0].orientation, "h")
        self.assertEqual(len(set(figure.data[0].marker.color)), len(rows))
        self.assertFalse(figure.data[0].showlegend)

    def test_aging_composition_is_horizontal_and_sums_to_one_hundred(self):
        rows = [
            {"Cola": "Consulta nueva", "Tramo": "0–30", "n": 3, "pct": 30},
            {"Cola": "Consulta nueva", "Tramo": ">90", "n": 7, "pct": 70},
        ]
        figure = build_100pct_stacked_figure(
            rows,
            row_key="Cola",
            segment_key="Tramo",
            count_key="n",
            percentage_key="pct",
            segment_order=["0–30", ">90"],
            color_map={"0–30": "#CCCCCC", ">90": "#B7791F"},
        )
        self.assertTrue(all(trace.orientation == "h" for trace in figure.data))
        self.assertEqual(sum(trace.x[0] for trace in figure.data), 100)
        self.assertGreaterEqual(figure.layout.height, MIN_CHART_HEIGHT)
        self.assertLessEqual(figure.layout.height, MAX_CHART_HEIGHT)

    def test_plotly_controls_are_responsive_and_modebar_is_hidden(self):
        self.assertIs(PLOTLY_CONFIG["responsive"], True)
        self.assertIs(PLOTLY_CONFIG["displayModeBar"], False)

    def test_two_period_chart_titles_are_not_named_trends(self):
        source = (REPO_ROOT / "dashboard/components/visuals.py").read_text(
            encoding="utf-8"
        )
        self.assertNotRegex(source, r'title\s*=\s*(?:f)?["\']Tendencia')

    def test_responsive_card_grid_does_not_use_fixed_or_sticky_positioning(self):
        source = (REPO_ROOT / "dashboard/components/design.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(".hec-metric-grid", source)
        self.assertIn("@media (max-width: 640px)", source)
        self.assertNotRegex(source, r"position\s*:\s*(fixed|sticky)")


if __name__ == "__main__":
    unittest.main()
