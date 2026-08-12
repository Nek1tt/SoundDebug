using System.Text.Json.Serialization;

namespace SoundDebug.Frontend.Models;

public sealed class AnalysisReport
{
    [JsonPropertyName("meta")] public MetaData Meta { get; set; } = new();
    [JsonPropertyName("loudness")] public LoudnessData Loudness { get; set; } = new();
    [JsonPropertyName("tonal")] public TonalData Tonal { get; set; } = new();
    [JsonPropertyName("stereo")] public StereoData Stereo { get; set; } = new();
    [JsonPropertyName("rhythm")] public RhythmData Rhythm { get; set; } = new();
    [JsonPropertyName("reference_comparison")] public ReferenceComparison? ReferenceComparison { get; set; }
    [JsonPropertyName("audio_ml")] public AudioMlData AudioMl { get; set; } = new();
    [JsonPropertyName("diagnostic_summary")] public DiagnosticSummary Summary { get; set; } = new();
    [JsonPropertyName("recommendations")] public List<DiagnosticFinding> Recommendations { get; set; } = new();
    [JsonPropertyName("additional_findings")] public List<DiagnosticFinding> AdditionalFindings { get; set; } = new();
    [JsonPropertyName("report_version")] public string ReportVersion { get; set; } = "p0";
    [JsonPropertyName("artistic_intent_warning")] public string ArtisticIntentWarning { get; set; } = "";
}

public sealed class MetaData
{
    [JsonPropertyName("duration_sec")] public double? Duration { get; set; }
    [JsonPropertyName("sample_rate")] public int? SampleRate { get; set; }
    [JsonPropertyName("num_channels")] public int? Channels { get; set; }
    [JsonPropertyName("analysis_version")] public string AnalysisVersion { get; set; } = "";
}

public sealed class LoudnessData
{
    [JsonPropertyName("integrated_lufs")] public double? Lufs { get; set; }
    [JsonPropertyName("true_peak_dbtp")] public double? TruePeak { get; set; }
    [JsonPropertyName("plr_lu")] public double? Plr { get; set; }
    [JsonPropertyName("short_term_loudness_spread_lu")] public double? ShortTermSpread { get; set; }
    [JsonPropertyName("crest_factor_db")] public double? CrestFactor { get; set; }
    [JsonPropertyName("clipping_count")] public int ClippingCount { get; set; }
}

public sealed class TonalData
{
    [JsonPropertyName("band_energy_pct")] public Dictionary<string, double> BandEnergyPct { get; set; } = new();
    [JsonPropertyName("representation")] public string Representation { get; set; } = "";
}

public sealed class StereoData
{
    [JsonPropertyName("stereo_width")] public double? Width { get; set; }
    [JsonPropertyName("phase_correlation")] public double? Phase { get; set; }
    [JsonPropertyName("minimum_phase_correlation")] public double? MinimumPhase { get; set; }
    [JsonPropertyName("mono_fold_down_loss_db")] public double? MonoLoss { get; set; }
    [JsonPropertyName("bass_side_energy_pct")] public double? BassSide { get; set; }
    [JsonPropertyName("channel_layout")] public string ChannelLayout { get; set; } = "";
}

public sealed class RhythmData
{
    [JsonPropertyName("bpm")] public double? Bpm { get; set; }
    [JsonPropertyName("estimated_key")] public string Key { get; set; } = "—";
    [JsonPropertyName("estimated_mode")] public string Mode { get; set; } = "";
    [JsonPropertyName("key_confidence")] public double KeyConfidence { get; set; }
}

public sealed class ReferenceComparison
{
    [JsonPropertyName("source")] public string Source { get; set; } = "genre-profile";
    [JsonPropertyName("reference_count")] public int ReferenceCount { get; set; }
    [JsonPropertyName("method")] public string Method { get; set; } = "";
    [JsonPropertyName("note")] public string Note { get; set; } = "";
    [JsonPropertyName("tonal_shape_difference")] public Dictionary<string, TonalDifference> Tonal { get; set; } = new();
    [JsonPropertyName("loudness_difference")] public DifferenceDimension? Loudness { get; set; }
    [JsonPropertyName("dynamics_difference")] public Dictionary<string, DifferenceDimension> Dynamics { get; set; } = new();
    [JsonPropertyName("stereo_difference")] public Dictionary<string, DifferenceDimension> Stereo { get; set; } = new();
}

public sealed class DifferenceDimension
{
    [JsonPropertyName("difference")] public double Difference { get; set; }
    [JsonPropertyName("unit")] public string Unit { get; set; } = "";
    [JsonPropertyName("support_count")] public int SupportCount { get; set; }
    [JsonPropertyName("reference_count")] public int ReferenceCount { get; set; }
    [JsonPropertyName("reliability")] public string Reliability { get; set; } = "LOW";
}

public sealed class TonalDifference
{
    [JsonPropertyName("difference_db")] public double Difference { get; set; }
    [JsonPropertyName("support_count")] public int SupportCount { get; set; }
    [JsonPropertyName("reference_count")] public int ReferenceCount { get; set; }
    [JsonPropertyName("reliability")] public string Reliability { get; set; } = "LOW";
}

public sealed class AudioMlData
{
    [JsonPropertyName("enabled")] public bool Enabled { get; set; }
    [JsonPropertyName("reason")] public string Reason { get; set; } = "";
    [JsonPropertyName("scores")] public Dictionary<string, double> Scores { get; set; } = new();
    [JsonPropertyName("caveat")] public string Caveat { get; set; } = "";
}

public sealed class DiagnosticSummary
{
    [JsonPropertyName("total")] public int Total { get; set; }
    [JsonPropertyName("facts")] public int Facts { get; set; }
    [JsonPropertyName("reference_differences")] public int ReferenceDifferences { get; set; }
    [JsonPropertyName("hypotheses")] public int Hypotheses { get; set; }
}

public sealed class DiagnosticFinding
{
    [JsonPropertyName("classification")] public string Classification { get; set; } = "HYPOTHESIS";
    [JsonPropertyName("title")] public string Title { get; set; } = "";
    [JsonPropertyName("priority")] public string Priority { get; set; } = "LOW";
    [JsonPropertyName("severity")] public string Severity { get; set; } = "info";
    [JsonPropertyName("reliability")] public string Reliability { get; set; } = "";
    [JsonPropertyName("reliability_reason")] public string ReliabilityReason { get; set; } = "";
    [JsonPropertyName("what_detected")] public string WhatDetected { get; set; } = "";
    [JsonPropertyName("why_attention")] public string WhyAttention { get; set; } = "";
    [JsonPropertyName("audible_meaning")] public string AudibleMeaning { get; set; } = "";
    [JsonPropertyName("possible_causes")] public List<string> PossibleCauses { get; set; } = new();
    [JsonPropertyName("daw_check_steps")] public List<string> DawCheckSteps { get; set; } = new();
    [JsonPropertyName("do_not_automate")] public string DoNotAutomate { get; set; } = "";
    [JsonPropertyName("reference_context")] public string? ReferenceContext { get; set; }
    [JsonPropertyName("evidence")] public List<string> Evidence { get; set; } = new();
    [JsonPropertyName("timestamps_sec")] public List<double> Timestamps { get; set; } = new();
}
