using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Serialization;
using Microsoft.JSInterop;

public class ReportService
{
    private readonly HttpClient _reportHttp;
    private readonly IJSRuntime _js;

    public ReportService(IHttpClientFactory factory, IJSRuntime js)
    {
        _reportHttp = factory.CreateClient("Report");
        _js = js;
    }

    public class ReportResponse
    {
        [JsonPropertyName("job_id")]
        public int JobId { get; set; }

        [JsonPropertyName("metrics")]
        public Dictionary<string, object> Metrics { get; set; } = new();
    }

    public async Task<ReportResponse?> GetReportAsync(int jobId)
    {
        var token = await _js.InvokeAsync<string>("localStorage.getItem", "authToken");

        if (string.IsNullOrWhiteSpace(token))
        {
            await _js.InvokeVoidAsync("console.log", "TOKEN IS NULL");
            return null;
        }

        _reportHttp.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

        var response = await _reportHttp.GetAsync($"reports/{jobId}");

        await _js.InvokeVoidAsync("console.log", "STATUS:", response.StatusCode);

        if (response.StatusCode == HttpStatusCode.NotFound) 
            return null;

        response.EnsureSuccessStatusCode();

        return await response.Content.ReadFromJsonAsync<ReportResponse>();
    }
}