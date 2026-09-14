import flet as ft
import flet_charts as fch

# Test LineChart construction
points = [
    fch.LineChartDataPoint(x=0, y=2, tooltip="Week 1: 2 lessons"),
    fch.LineChartDataPoint(x=1, y=5, tooltip="Week 2: 5 lessons"),
    fch.LineChartDataPoint(x=2, y=8, tooltip="Week 3: 8 lessons"),
    fch.LineChartDataPoint(x=3, y=14, tooltip="Week 4: 14 lessons"),
]

series = fch.LineChartData(
    points=points,
    curved=True,
    curve_smoothness=0.35,
    stroke_width=3,
    color=ft.Colors.PRIMARY,
    point=fch.ChartCirclePoint(radius=4, color=ft.Colors.PRIMARY),
    below_line_bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
    prevent_curve_over_shooting=True,
)

labels = [
    fch.ChartAxisLabel(value=0, label=ft.Text("W1", size=10)),
    fch.ChartAxisLabel(value=1, label=ft.Text("W2", size=10)),
    fch.ChartAxisLabel(value=2, label=ft.Text("W3", size=10)),
    fch.ChartAxisLabel(value=3, label=ft.Text("W4", size=10)),
]

chart = fch.LineChart(
    data_series=[series],
    min_y=0,
    max_y=16,
    min_x=0,
    max_x=3,
    bottom_axis=fch.ChartAxis(labels=labels),
    horizontal_grid_lines=fch.ChartGridLines(
        color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
        dash_pattern=[4, 4],
        width=1,
    ),
    tooltip=fch.LineChartTooltip(bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST),
    interactive=True,
    expand=True,
)

print("LineChart instantiated successfully:", type(chart))
