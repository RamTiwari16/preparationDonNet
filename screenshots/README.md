# screenshots/ — reference diagrams and your own screenshots

Everything in this folder that starts with a **two-digit section number** is picked up by `build.py`
and shown in a *Reference diagrams & screenshots* panel at the top of that section in `index.html`.

| Prefix | Section | Prefix | Section |
|---|---|---|---|
| `00-` | Home page | `13-` | Docker |
| `01-` | C# — Core & Advanced | `14-` | Kubernetes |
| `02-` | .NET / ASP.NET Core | `15-` | Microservices |
| `03-` | Dependency Injection | `16-` | Caching |
| `04-` | Authentication & Authorization | `17-` | System Design — HLD |
| `05-` | Entity Framework Core | `18-` | LLD |
| `06-` | SQL Server | `19-` | Real-world system designs |
| `07-` | Coding / DSA | `20-` | Performance |
| `08-` | JavaScript | `21-` | Observability |
| `09-` | React | `22-` | AI / GenAI |
| `10-` | Angular | `23-` | HR / Client round |
| `11-` | Azure | `24-` | Coding questions |
| `12-` | Azure DevOps / CI-CD | `25-` | SQL coding questions |

## Included diagrams

The `.svg` files here were drawn for this site (they are diagrams, not captures of real tools).
Each has its caption inside the file (`<title>`).

## Adding your own screenshots

1. Save the image as `NN-short-description.png` (also `.jpg`, `.webp`, `.gif` or `.svg`).
   Example: `05-ef-core-generated-sql.png` appears under **Entity Framework Core**.
   Hyphens become spaces in the caption: "Ef core generated sql".
2. Rebuild: double-click `build.bat` in the project root (or run `python tools/build.py`).
3. Refresh `index.html` — the image shows up as a *screenshot* card; click it to enlarge
   (arrow keys move between images, Esc closes).

Good candidates to capture yourself: Swagger UI for your API, Postman requests with a JWT, SSMS execution
plans, Azure Portal blades (App Service, Key Vault, Application Insights), Azure DevOps pipeline runs,
Docker Desktop, `kubectl` output, Application Insights Application Map.
