import { describe, it, expect } from "vitest";
import {
  getConfidenceColor,
  getHrvRhrColor,
  getHrvRhrLabel,
  getSleepDebtColor,
  getAcwrColor,
  getAcwrLabel,
  getStepsChangeColor,
  getWeightChangeColor,
  getStressTrendColor,
  getCorrelationColor,
  getHrvSdColor,
  getTsbColor,
  getAllostaticScoreColor,
  getCrossCorrelationColor,
  signPrefix,
  formatDaysLabel,
} from "@/features/dashboard/statistics/stat-utils";

describe("getConfidenceColor", () => {
  it("returns green for high confidence", () => {
    expect(getConfidenceColor(0.8)).toBe("text-green-500");
    expect(getConfidenceColor(0.95)).toBe("text-green-500");
    expect(getConfidenceColor(1.0)).toBe("text-green-500");
  });

  it("returns yellow for moderate confidence", () => {
    expect(getConfidenceColor(0.6)).toBe("text-yellow-500");
    expect(getConfidenceColor(0.7)).toBe("text-yellow-500");
    expect(getConfidenceColor(0.79)).toBe("text-yellow-500");
  });

  it("returns red for low confidence", () => {
    expect(getConfidenceColor(0.59)).toBe("text-red-500");
    expect(getConfidenceColor(0.3)).toBe("text-red-500");
    expect(getConfidenceColor(0)).toBe("text-red-500");
  });
});

describe("getHrvRhrColor", () => {
  it("returns muted for null", () => {
    expect(getHrvRhrColor(null)).toBe("text-muted-foreground");
  });

  it("returns red when body under strain (> 1)", () => {
    expect(getHrvRhrColor(1.5)).toBe("text-red-500");
    expect(getHrvRhrColor(3.0)).toBe("text-red-500");
  });

  it("returns green when well recovered (< -1)", () => {
    expect(getHrvRhrColor(-1.5)).toBe("text-green-500");
    expect(getHrvRhrColor(-3.0)).toBe("text-green-500");
  });

  it("returns blue when balanced", () => {
    expect(getHrvRhrColor(0)).toBe("text-blue-500");
    expect(getHrvRhrColor(0.5)).toBe("text-blue-500");
    expect(getHrvRhrColor(-0.5)).toBe("text-blue-500");
    expect(getHrvRhrColor(1.0)).toBe("text-blue-500");
    expect(getHrvRhrColor(-1.0)).toBe("text-blue-500");
  });
});

describe("getHrvRhrLabel", () => {
  it("returns descriptive labels for each state", () => {
    expect(getHrvRhrLabel(null)).toBe("Insufficient data");
    expect(getHrvRhrLabel(2.0)).toBe("Body under strain");
    expect(getHrvRhrLabel(-2.0)).toBe("Well recovered");
    expect(getHrvRhrLabel(0)).toBe("Balanced");
  });
});

describe("getSleepDebtColor", () => {
  it("returns red for high sleep debt", () => {
    expect(getSleepDebtColor(121)).toBe("text-red-500");
    expect(getSleepDebtColor(200)).toBe("text-red-500");
  });

  it("returns yellow for moderate sleep debt", () => {
    expect(getSleepDebtColor(61)).toBe("text-yellow-500");
    expect(getSleepDebtColor(120)).toBe("text-yellow-500");
  });

  it("returns green for low sleep debt", () => {
    expect(getSleepDebtColor(60)).toBe("text-green-500");
    expect(getSleepDebtColor(0)).toBe("text-green-500");
  });
});

describe("getAcwrColor", () => {
  it("returns muted for null", () => {
    expect(getAcwrColor(null)).toBe("text-muted-foreground");
  });

  it("returns red for injury risk (> 1.5)", () => {
    expect(getAcwrColor(1.6)).toBe("text-red-500");
    expect(getAcwrColor(2.0)).toBe("text-red-500");
  });

  it("returns yellow for detraining risk (< 0.8)", () => {
    expect(getAcwrColor(0.5)).toBe("text-yellow-500");
    expect(getAcwrColor(0.79)).toBe("text-yellow-500");
  });

  it("returns green for sweet spot", () => {
    expect(getAcwrColor(0.8)).toBe("text-green-500");
    expect(getAcwrColor(1.0)).toBe("text-green-500");
    expect(getAcwrColor(1.5)).toBe("text-green-500");
  });
});

describe("getAcwrLabel", () => {
  it("returns appropriate labels", () => {
    expect(getAcwrLabel(null)).toBe("Insufficient strain data");
    expect(getAcwrLabel(1.6)).toBe("Injury risk - reduce load");
    expect(getAcwrLabel(0.5)).toBe("Detraining risk");
    expect(getAcwrLabel(1.0)).toBe("Sweet spot");
  });
});

describe("getStepsChangeColor", () => {
  it("returns muted for null", () => {
    expect(getStepsChangeColor(null)).toBe("text-muted-foreground");
  });

  it("returns red for large decrease", () => {
    expect(getStepsChangeColor(-1500)).toBe("text-red-500");
  });

  it("returns green for large increase", () => {
    expect(getStepsChangeColor(1500)).toBe("text-green-500");
  });

  it("returns blue for small change", () => {
    expect(getStepsChangeColor(500)).toBe("text-blue-500");
    expect(getStepsChangeColor(-500)).toBe("text-blue-500");
    expect(getStepsChangeColor(0)).toBe("text-blue-500");
  });
});

describe("getWeightChangeColor", () => {
  it("returns empty for null", () => {
    expect(getWeightChangeColor(null)).toBe("");
  });

  it("returns red for weight gain > 0.5", () => {
    expect(getWeightChangeColor(0.6)).toBe("text-red-500");
    expect(getWeightChangeColor(2.0)).toBe("text-red-500");
  });

  it("returns green for weight loss < -0.5", () => {
    expect(getWeightChangeColor(-0.6)).toBe("text-green-500");
  });

  it("returns blue for stable weight", () => {
    expect(getWeightChangeColor(0.3)).toBe("text-blue-500");
    expect(getWeightChangeColor(-0.3)).toBe("text-blue-500");
    expect(getWeightChangeColor(0)).toBe("text-blue-500");
  });
});

describe("getStressTrendColor", () => {
  it("returns empty for null", () => {
    expect(getStressTrendColor(null)).toBe("");
  });

  it("returns red for increasing stress", () => {
    expect(getStressTrendColor(6)).toBe("text-red-500");
  });

  it("returns green for decreasing stress", () => {
    expect(getStressTrendColor(-6)).toBe("text-green-500");
  });

  it("returns blue for stable stress", () => {
    expect(getStressTrendColor(3)).toBe("text-blue-500");
    expect(getStressTrendColor(0)).toBe("text-blue-500");
  });
});

describe("getCorrelationColor", () => {
  it("returns muted for null", () => {
    expect(getCorrelationColor(null)).toBe("text-muted-foreground");
  });

  it("returns green for negative correlation (good HRV-RHR)", () => {
    expect(getCorrelationColor(-0.5)).toBe("text-green-500");
  });

  it("returns red for positive correlation", () => {
    expect(getCorrelationColor(0.1)).toBe("text-red-500");
  });

  it("returns muted for weak negative correlation", () => {
    expect(getCorrelationColor(-0.2)).toBe("text-muted-foreground");
  });
});

describe("getHrvSdColor", () => {
  it("returns empty for null", () => {
    expect(getHrvSdColor(null)).toBe("");
  });

  it("returns green for low variability", () => {
    expect(getHrvSdColor(0.05)).toBe("text-green-500");
    expect(getHrvSdColor(0.09)).toBe("text-green-500");
  });

  it("returns red for high variability", () => {
    expect(getHrvSdColor(0.2)).toBe("text-red-500");
  });

  it("returns empty for moderate variability", () => {
    expect(getHrvSdColor(0.12)).toBe("");
  });
});

describe("getTsbColor", () => {
  it("returns empty for null", () => {
    expect(getTsbColor(null)).toBe("");
  });

  it("returns green for positive TSB (fresh)", () => {
    expect(getTsbColor(5)).toBe("text-green-500");
  });

  it("returns red for very negative TSB (fatigued)", () => {
    expect(getTsbColor(-15)).toBe("text-red-500");
  });

  it("returns empty for moderate fatigue", () => {
    expect(getTsbColor(-5)).toBe("");
    expect(getTsbColor(0)).toBe("");
  });
});

describe("getAllostaticScoreColor", () => {
  it("returns yellow for null", () => {
    expect(getAllostaticScoreColor(null)).toBe("text-yellow-500");
  });

  it("returns green for low allostatic load", () => {
    expect(getAllostaticScoreColor(10)).toBe("text-green-500");
    expect(getAllostaticScoreColor(19)).toBe("text-green-500");
  });

  it("returns red for high allostatic load", () => {
    expect(getAllostaticScoreColor(50)).toBe("text-red-500");
  });

  it("returns yellow for moderate allostatic load", () => {
    expect(getAllostaticScoreColor(30)).toBe("text-yellow-500");
  });
});

describe("getCrossCorrelationColor", () => {
  it("returns empty for null", () => {
    expect(getCrossCorrelationColor(null)).toBe("");
  });

  it("returns green for strong positive correlation", () => {
    expect(getCrossCorrelationColor(0.5)).toBe("text-green-500");
  });

  it("returns red for strong negative correlation", () => {
    expect(getCrossCorrelationColor(-0.5)).toBe("text-red-500");
  });

  it("returns empty for weak correlation", () => {
    expect(getCrossCorrelationColor(0.1)).toBe("");
    expect(getCrossCorrelationColor(-0.1)).toBe("");
  });
});

describe("signPrefix", () => {
  it("returns + for positive values", () => {
    expect(signPrefix(5)).toBe("+");
    expect(signPrefix(0.1)).toBe("+");
  });

  it("returns empty for zero and negative values", () => {
    expect(signPrefix(0)).toBe("");
    expect(signPrefix(-5)).toBe("");
  });
});

describe("formatDaysLabel", () => {
  it("formats days as days for small values", () => {
    expect(formatDaysLabel(7)).toBe("7d");
    expect(formatDaysLabel(28)).toBe("28d");
    expect(formatDaysLabel(29)).toBe("29d");
  });

  it("formats as months for 30+ days", () => {
    expect(formatDaysLabel(30)).toBe("1M");
    expect(formatDaysLabel(90)).toBe("3M");
    expect(formatDaysLabel(252)).toBe("8M");
  });

  it("formats as years for 365+ days", () => {
    expect(formatDaysLabel(365)).toBe("1Y");
    expect(formatDaysLabel(730)).toBe("2Y");
  });
});
