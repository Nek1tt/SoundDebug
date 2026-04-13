using Microsoft.JSInterop;
using Microsoft.AspNetCore.Components.Forms;
using System.Net.Http.Headers;
using SoundDebug.Frontend.Models;
using System.Text.Json;
public class UploadService
{
    private readonly HttpClient _uploadHttp;
    private readonly IJSRuntime _js;

    public UploadService(IHttpClientFactory factory, IJSRuntime js)
    {
        _uploadHttp = factory.CreateClient("Upload");
        _js = js;
    }

    public async Task<string?> CreateJob(string genre, IBrowserFile file)
    {
        var token = await _js.InvokeAsync<string>("localStorage.getItem", "authToken");

        _uploadHttp.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

        using var content = new MultipartFormDataContent();

        content.Add(new StringContent(genre), "genre");

        var stream = file.OpenReadStream(50 * 1024 * 1024);
        content.Add(new StreamContent(stream), "file", file.Name);

        var response = await _uploadHttp.PostAsync("jobs", content);
        var body = await response.Content.ReadAsStringAsync();
        await _js.InvokeVoidAsync("console.log", body);

        if (!response.IsSuccessStatusCode)
            return null;

        return await response.Content.ReadAsStringAsync();
    }

    public async Task<List<JobModel?>> GetJobs()
    {
        var token = await _js.InvokeAsync<string>("localStorage.getItem", "authToken");
        _uploadHttp.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

        var response = await _uploadHttp.GetAsync("jobs");
        if (!response.IsSuccessStatusCode)
            return null;

        await _js.InvokeVoidAsync("console.log", "Токен:", response);

        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<List<JobModel>>(json);
    }
}