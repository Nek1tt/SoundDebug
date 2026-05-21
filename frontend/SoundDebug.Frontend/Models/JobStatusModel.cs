using System.Text.Json.Serialization;

namespace SoundDebug.Frontend.Models {
    public class JobStatusModel
    {
        [JsonPropertyName("job_id")]
        public int JobId { get; set; }

        [JsonPropertyName("status")]
        public string Status { get; set; } = "";
        [JsonPropertyName("progress")]
        public int Progress { get; set; }
    }
}