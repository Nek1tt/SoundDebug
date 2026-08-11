using System.Text.Json.Serialization;

namespace SoundDebug.Frontend.Models {
    public class UserModel
    {
        [JsonPropertyName("id")]
        public int Id { get; set; }
        [JsonPropertyName("email")]
        public string Email { get; set; } = "";
    }
}