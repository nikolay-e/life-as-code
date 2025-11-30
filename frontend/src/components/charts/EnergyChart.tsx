import Plot from "react-plotly.js";
import type { EnergyData } from "@/types/health";

interface Props {
  data: EnergyData[];
}

export default function EnergyChart({ data }: Props) {
  if (!data.length) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Energy Expenditure
        </h3>
        <div className="h-64 flex items-center justify-center text-gray-500">
          No energy data available
        </div>
      </div>
    );
  }

  const dates = data.map((d) => d.date);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Energy Expenditure
      </h3>
      <Plot
        data={[
          {
            x: dates,
            y: data.map((d) => d.active_energy),
            type: "scatter",
            mode: "lines+markers",
            name: "Active (kcal)",
            line: { color: "#dc3545" },
            marker: { size: 6 },
          },
          {
            x: dates,
            y: data.map((d) => d.basal_energy),
            type: "scatter",
            mode: "lines+markers",
            name: "Basal (kcal)",
            line: { color: "#007bff" },
            marker: { size: 6 },
          },
          {
            x: dates,
            y: data.map((d) => (d.active_energy || 0) + (d.basal_energy || 0)),
            type: "scatter",
            mode: "lines",
            name: "Total (kcal)",
            line: { color: "#28a745", dash: "dot" },
            visible: "legendonly",
          },
        ]}
        layout={{
          autosize: true,
          height: 300,
          margin: { l: 60, r: 30, t: 20, b: 40 },
          showlegend: true,
          legend: { orientation: "h", y: -0.2 },
          xaxis: { title: { text: "" } },
          yaxis: { title: { text: "Calories (kcal)" } },
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: "100%" }}
      />
    </div>
  );
}
