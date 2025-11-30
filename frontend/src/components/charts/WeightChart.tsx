import Plot from "react-plotly.js";
import type { WeightData } from "@/types/health";

interface Props {
  data: WeightData[];
}

export default function WeightChart({ data }: Props) {
  if (!data.length) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Weight & Body Composition
        </h3>
        <div className="h-64 flex items-center justify-center text-gray-500">
          No weight data available
        </div>
      </div>
    );
  }

  const dates = data.map((d) => d.date);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Weight & Body Composition
      </h3>
      <Plot
        data={[
          {
            x: dates,
            y: data.map((d) => d.weight_kg),
            type: "scatter",
            mode: "lines+markers",
            name: "Weight (kg)",
            line: { color: "#007bff" },
            marker: { size: 6 },
          },
          {
            x: dates,
            y: data.map((d) => d.bmi),
            type: "scatter",
            mode: "lines+markers",
            name: "BMI",
            yaxis: "y2",
            line: { color: "#28a745" },
            marker: { size: 6 },
          },
          {
            x: dates,
            y: data.map((d) => d.body_fat_pct),
            type: "scatter",
            mode: "lines+markers",
            name: "Body Fat %",
            yaxis: "y3",
            line: { color: "#dc3545" },
            marker: { size: 6 },
            visible: "legendonly",
          },
          {
            x: dates,
            y: data.map((d) => d.muscle_mass_kg),
            type: "scatter",
            mode: "lines+markers",
            name: "Muscle Mass (kg)",
            yaxis: "y4",
            line: { color: "#ffc107" },
            marker: { size: 6 },
            visible: "legendonly",
          },
        ]}
        layout={{
          autosize: true,
          height: 300,
          margin: { l: 50, r: 50, t: 20, b: 40 },
          showlegend: true,
          legend: { orientation: "h", y: -0.2 },
          xaxis: { title: { text: "" } },
          yaxis: { title: { text: "Weight (kg)" }, side: "left" },
          yaxis2: { title: { text: "BMI" }, overlaying: "y", side: "right" },
          yaxis3: {
            title: { text: "Body Fat %" },
            overlaying: "y",
            side: "left",
            visible: false,
          },
          yaxis4: {
            title: { text: "Muscle (kg)" },
            overlaying: "y",
            side: "right",
            visible: false,
          },
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: "100%" }}
      />
    </div>
  );
}
