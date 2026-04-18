FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY GeoPulse.Api/GeoPulse.Api.csproj GeoPulse.Api/
RUN dotnet restore GeoPulse.Api/GeoPulse.Api.csproj
COPY GeoPulse.Api/ GeoPulse.Api/
RUN dotnet publish GeoPulse.Api/GeoPulse.Api.csproj -c Release -o /app

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app
COPY --from=build /app .
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080
ENTRYPOINT ["dotnet", "GeoPulse.Api.dll"]
