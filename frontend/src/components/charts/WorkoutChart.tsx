import Plot from "react-plotly.js";
import type { WorkoutData } from "@/types/health";

interface Props {
  data: WorkoutData[];
}

export default function WorkoutChart({ data }: Props) {
  if (!data.length) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Workout Volume
        </h3>
        <div className="h-64 flex items-center justify-center text-gray-500">
          No workout data available
        </div>
      </div>
    );
  }

  const dates = data.map((d) => d.date);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Workout Volume
      </h3>
      <Plot
        data={[
          {
            x: dates,
            y: data.map((d) => d.total_volume),
            type: "bar",
            name: "Volume (kg×reps)",
            marker: { color: "#007bff" },
          },
          {
            x: dates,
            y: data.map((d) => d.total_sets),
            type: "scatter",
            mode: "lines+markers",
            name: "Total Sets",
            yaxis: "y2",
            line: { color: "#28a745" },
            marker: { size: 8 },
          },
        ]}
        layout={{
          autosize: true,
          height: 300,
          margin: { l: 60, r: 60, t: 20, b: 40 },
          showlegend: true,
          legend: { orientation: "h", y: -0.2 },
          xaxis: { title: { text: "" } },
          yaxis: { title: { text: "Volume (kg×reps)" }, side: "left" },
          yaxis2: { title: { text: "Sets" }, overlaying: "y", side: "right" },
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: "100%" }}
      />
    </div>
  );
}
