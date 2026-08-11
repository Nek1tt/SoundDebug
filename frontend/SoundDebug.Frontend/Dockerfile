FROM mcr.microsoft.com/dotnet/sdk:8.0-alpine AS build
WORKDIR /src
COPY frontend/SoundDebug.Frontend/SoundDebug.Frontend.csproj ./
RUN dotnet restore SoundDebug.Frontend.csproj
COPY frontend/SoundDebug.Frontend/ ./
RUN dotnet publish SoundDebug.Frontend.csproj -c Release -o /publish

FROM nginx:1.27-alpine
COPY frontend/SoundDebug.Frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /publish/wwwroot /usr/share/nginx/html
EXPOSE 80
