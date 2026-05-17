using System.Net.Http.Headers;
using System.Net.Http.Json;
using Microsoft.IdentityModel.Tokens;
using Microsoft.JSInterop;
using Microsoft.VisualBasic;
using SoundDebug.Frontend.Models;

public class AuthService
{
    private readonly HttpClient _authHttp;
    private readonly IJSRuntime _js;

    public bool IsAuthenticated { get; private set; } = false;
    public string? Token { get; private set; }

    public AuthService(IHttpClientFactory factory, IJSRuntime js)
    {
        _authHttp = factory.CreateClient("Auth");
        _js = js;
    }

    public async Task<bool> LoginAsync(string email, string password)
    {
        var response = await _authHttp.PostAsJsonAsync("/auth/login", new { email, password });
        if (!response.IsSuccessStatusCode) return false;

        var result = await response.Content.ReadFromJsonAsync<AuthResponse>();
        if (result == null) return false;

        Token = result.access_token;
        await _js.InvokeVoidAsync("localStorage.setItem", "authToken", Token);
        IsAuthenticated = true;

        _authHttp.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", Token);
        return true;
    }

    public async Task<bool> RegisterAsync(string email, string password)
    {
        var response = await _authHttp.PostAsJsonAsync("/auth/register", new { email, password });
        if (!response.IsSuccessStatusCode) return false;

        var result = await response.Content.ReadFromJsonAsync<AuthResponse>();
        if (result == null) return false;

        Token = result.access_token;
        await _js.InvokeVoidAsync("localStorage.setItem", "authToken", Token);
        IsAuthenticated = true;

        _authHttp.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", Token);

        return true;
    }

    public async Task LogoutAsync()
    {
        Token = null;
        IsAuthenticated = false;
        await _js.InvokeVoidAsync("localStorage.removeItem", "authToken");
        _authHttp.DefaultRequestHeaders.Authorization = null;
    }

    public async Task InitializeAsync()
    {
        Token = await _js.InvokeAsync<string>("localStorage.getItem", "authToken");
        if (!string.IsNullOrEmpty(Token))
        {
            IsAuthenticated = true;
            _authHttp.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", Token);
        }
    }

    public async Task<UserModel?> GetMeAsync()
    {
        try
        {
            var token = await _js.InvokeAsync<string>("localStorage.getItem", "authToken");

            if (string.IsNullOrWhiteSpace(token)) return null;

            var encodedToken = Uri.EscapeDataString(token);
            // await _js.InvokeVoidAsync("console.log", "Токен:", encodedToken);

            var response = await _authHttp.GetAsync($"/auth/me?token={encodedToken}");

            if (!response.IsSuccessStatusCode)
                return null;

            var user = await response.Content.ReadFromJsonAsync<UserModel>();

            return user;
        }
        catch
        {
            return null;
        }
    }
}

public class AuthResponse
{
    public string access_token { get; set; } = "";
    public string token_type { get; set; } = "";
}