import Plot from "react-plotly.js";
import type { StepsData } from "@/types/health";

interface Props {
  data: StepsData[];
}

export default function StepsChart({ data }: Props) {
  if (!data.length) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Steps & Distance
        </h3>
        <div className="h-64 flex items-center justify-center text-gray-500">
          No steps data available
        </div>
      </div>
    );
  }

  const dates = data.map((d) => d.date);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Steps & Distance
      </h3>
      <Plot
        data={[
          {
            x: dates,
            y: data.map((d) => d.total_steps),
            type: "bar",
            name: "Steps",
            marker: { color: "#28a745" },
          },
          {
            x: dates,
            y: data.map((d) =>
              d.total_distance ? d.total_distance / 1000 : null,
            ),
            type: "scatter",
            mode: "lines+markers",
            name: "Distance (km)",
            yaxis: "y2",
            line: { color: "#007bff" },
            marker: { size: 6 },
          },
          {
            x: dates,
            y: data.map((d) => d.step_goal),
            type: "scatter",
            mode: "lines",
            name: "Goal",
            line: { color: "#dc3545", dash: "dash" },
            visible: "legendonly",
          },
        ]}
        layout={{
          autosize: true,
          height: 300,
          margin: { l: 60, r: 60, t: 20, b: 40 },
          showlegend: true,
          legend: { orientation: "h", y: -0.2 },
          xaxis: { title: { text: "" } },
          yaxis: { title: { text: "Steps" }, side: "left" },
          yaxis2: {
            title: { text: "Distance (km)" },
            overlaying: "y",
            side: "right",
          },
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: "100%" }}
      />
    </div>
  );
}
