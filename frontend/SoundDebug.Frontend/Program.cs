using Microsoft.AspNetCore.Components.Web;
using Microsoft.AspNetCore.Components.WebAssembly.Hosting;
using SoundDebug.Frontend;

var builder = WebAssemblyHostBuilder.CreateDefault(args);
builder.RootComponents.Add<App>("#app");
builder.RootComponents.Add<HeadOutlet>("head::after");

var configuredApi = builder.Configuration["ApiBaseUrl"] ?? "api/";
var apiBase = Uri.TryCreate(configuredApi, UriKind.Absolute, out var absoluteApi)
    ? absoluteApi
    : new Uri(new Uri(builder.HostEnvironment.BaseAddress), configuredApi);

builder.Services.AddHttpClient("Auth", client => client.BaseAddress = apiBase);
builder.Services.AddHttpClient("Upload", client => client.BaseAddress = apiBase);
builder.Services.AddHttpClient("Report", client => client.BaseAddress = apiBase);

builder.Services.AddHttpClient();
builder.Services.AddScoped<AuthService>();
builder.Services.AddScoped<UploadService>();
builder.Services.AddScoped<ReportService>();

await builder.Build().RunAsync();
