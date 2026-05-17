using Microsoft.AspNetCore.Components.Web;
using Microsoft.AspNetCore.Components.WebAssembly.Hosting;
using SoundDebug.Frontend;

var builder = WebAssemblyHostBuilder.CreateDefault(args);
builder.RootComponents.Add<App>("#app");
builder.RootComponents.Add<HeadOutlet>("head::after");

builder.Services.AddHttpClient("Auth", client =>
{
    client.BaseAddress = new Uri("http://localhost:8001/");
});

builder.Services.AddHttpClient("Upload", client =>
{
    client.BaseAddress = new Uri("http://localhost:8002/");
});

builder.Services.AddHttpClient("Report", client =>
{
    client.BaseAddress = new Uri("http://localhost:8003/");
});

builder.Services.AddHttpClient();
builder.Services.AddScoped<AuthService>();
builder.Services.AddScoped<UploadService>();
builder.Services.AddScoped<ReportService>();

await builder.Build().RunAsync();
