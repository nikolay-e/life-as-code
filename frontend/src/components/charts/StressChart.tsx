import Plot from "react-plotly.js";
import type { StressData } from "@/types/health";

interface Props {
  data: StressData[];
}

export default function StressChart({ data }: Props) {
  if (!data.length) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Stress Level
        </h3>
        <div className="h-64 flex items-center justify-center text-gray-500">
          No stress data available
        </div>
      </div>
    );
  }

  const dates = data.map((d) => d.date);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Stress Level</h3>
      <Plot
        data={[
          {
            x: dates,
            y: data.map((d) => d.avg_stress),
            type: "scatter",
            mode: "lines+markers",
            name: "Avg Stress",
            line: { color: "#ffc107" },
            marker: { size: 6 },
            fill: "tozeroy",
            fillcolor: "rgba(255, 193, 7, 0.1)",
          },
          {
            x: dates,
            y: data.map((d) => d.max_stress),
            type: "scatter",
            mode: "lines",
            name: "Max Stress",
            line: { color: "#dc3545", dash: "dot" },
            visible: "legendonly",
          },
        ]}
        layout={{
          autosize: true,
          height: 300,
          margin: { l: 50, r: 30, t: 20, b: 40 },
          showlegend: true,
          legend: { orientation: "h", y: -0.2 },
          xaxis: { title: { text: "" } },
          yaxis: { title: { text: "Stress Level" }, range: [0, 100] },
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: "100%" }}
      />
    </div>
  );
}
