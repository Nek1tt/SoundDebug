using System.Text.Json.Serialization;

namespace SoundDebug.Frontend.Models {
    public class ReportResponse {
        [JsonPropertyName("job_id")]
        public int JobId { get; set; }

        [JsonPropertyName("metrics")]
        public Dictionary<string, object> Metrics { get; set; } = new();
    }
}

