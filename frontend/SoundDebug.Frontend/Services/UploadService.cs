using Microsoft.JSInterop;
using Microsoft.AspNetCore.Components.Forms;
using System.Net.Http.Headers;
using SoundDebug.Frontend.Models;
using System.Text.Json;
using System.Text.Json.Serialization;
public class UploadService
{
    private readonly HttpClient _uploadHttp;
    private readonly IJSRuntime _js;

    public UploadService(IHttpClientFactory factory, IJSRuntime js)
    {
        _uploadHttp = factory.CreateClient("Upload");
        _js = js;
    }

    public async Task<string> CreateJob(
        string genre,
        IBrowserFile file,
        IReadOnlyList<IBrowserFile> references,
        bool stemAnalysis)
    {
        var token = await GetRequiredTokenAsync();

        using var content = new MultipartFormDataContent();

        content.Add(new StringContent(genre), "genre");
        content.Add(new StringContent(stemAnalysis.ToString().ToLowerInvariant()), "stem_analysis");

        var stream = file.OpenReadStream(50 * 1024 * 1024);
        var trackContent = new StreamContent(stream);
        if (!string.IsNullOrWhiteSpace(file.ContentType))
            trackContent.Headers.ContentType = new MediaTypeHeaderValue(file.ContentType);
        content.Add(trackContent, "file", file.Name);

        foreach (var reference in references.Take(3))
        {
            var referenceStream = reference.OpenReadStream(50 * 1024 * 1024);
            var referenceContent = new StreamContent(referenceStream);
            if (!string.IsNullOrWhiteSpace(reference.ContentType))
                referenceContent.Headers.ContentType = new MediaTypeHeaderValue(reference.ContentType);
            content.Add(referenceContent, "references", reference.Name);
        }

        using var request = CreateAuthenticatedRequest(HttpMethod.Post, "jobs", token);
        request.Content = content;
        using var response = await _uploadHttp.SendAsync(request);
        var body = await response.Content.ReadAsStringAsync();
        await _js.InvokeVoidAsync("console.log", body);

        ThrowIfAuthenticationFailed(response);
        if (!response.IsSuccessStatusCode)
            throw new InvalidOperationException($"Не удалось создать анализ: {body}");

        return body;
    }

    public async Task<List<JobModel>?> GetJobs()
    {
        var token = await GetRequiredTokenAsync();
        using var request = CreateAuthenticatedRequest(HttpMethod.Get, "jobs", token);
        using var response = await _uploadHttp.SendAsync(request);
        ThrowIfAuthenticationFailed(response);
        if (!response.IsSuccessStatusCode)
            return null;

        // await _js.InvokeVoidAsync("console.log", "Задачи:", response);

        var json = await response.Content.ReadAsStringAsync();

        return JsonSerializer.Deserialize<List<JobModel>>(json)!;
    }

    public async Task<JobModel?> GetJob(int jobId)
    {
        var token = await GetRequiredTokenAsync();
        using var request = CreateAuthenticatedRequest(HttpMethod.Get, $"jobs/{jobId}", token);
        using var response = await _uploadHttp.SendAsync(request);
        ThrowIfAuthenticationFailed(response);
        if (!response.IsSuccessStatusCode)
            return null;

        // await _js.InvokeVoidAsync("console.log", "Задача:", response);

        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<JobModel>(json);
    }

    public async Task<JobStatusModel?> GetJobStatus(int jobId)
    {
        var token = await GetRequiredTokenAsync();
        using var request = CreateAuthenticatedRequest(HttpMethod.Get, $"jobs/{jobId}/status", token);
        using var response = await _uploadHttp.SendAsync(request);
        ThrowIfAuthenticationFailed(response);
        if (!response.IsSuccessStatusCode)
            return null;

        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<JobStatusModel>(json);
    }

    public async Task<bool> DeleteJob(int jobId)
    {
        var token = await GetRequiredTokenAsync();
        using var request = CreateAuthenticatedRequest(HttpMethod.Delete, $"jobs/{jobId}", token);
        using var response = await _uploadHttp.SendAsync(request);
        ThrowIfAuthenticationFailed(response);
        return response.IsSuccessStatusCode;
    }

    private async Task<string> GetRequiredTokenAsync()
    {
        var token = await _js.InvokeAsync<string?>("localStorage.getItem", "authToken");
        if (string.IsNullOrWhiteSpace(token))
            throw new UnauthorizedAccessException("Для запуска анализа необходимо войти в аккаунт.");

        return token;
    }

    private static HttpRequestMessage CreateAuthenticatedRequest(
        HttpMethod method,
        string uri,
        string token)
    {
        var request = new HttpRequestMessage(method, uri);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        return request;
    }

    private static void ThrowIfAuthenticationFailed(HttpResponseMessage response)
    {
        if (response.StatusCode is System.Net.HttpStatusCode.Unauthorized
            or System.Net.HttpStatusCode.Forbidden)
        {
            throw new UnauthorizedAccessException(
                "Сессия завершилась. Войдите в аккаунт повторно.");
        }
    }
}
