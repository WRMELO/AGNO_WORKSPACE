import os
import git
from rich.console import Console
from rich.table import Table

console = Console()


def run_audit():
    console.print("[bold blue]🚀 AGNO T002: Auditoria de Integridade (SSD Local)[/bold blue]")

    # Check 1: Estrutura Física
    paths = ["00_Strategy", "01_Architecture", "python_path.conf", ".gitignore", ".obsidian"]
    table = Table(title="Checagem de Arquivos")
    table.add_column("Caminho", style="cyan")
    table.add_column("Status", style="green")

    all_good = True
    for p in paths:
        if os.path.exists(p):
            table.add_row(p, "✅ OK")
        else:
            if p == ".obsidian":
                table.add_row(p, "⚠️  Ausente (Abra o Obsidian para criar)")
            else:
                table.add_row(p, "❌ FALTANDO")
                all_good = False
    console.print(table)

    # Check 2: Git Ignore (Prova de Fogo)
    try:
        repo = git.Repo(".")
        console.print(f"\n[bold]Git Status:[/bold] branch={repo.active_branch.name}")

        # Simula o que o Git vê
        untracked = repo.untracked_files

        # Teste de Lixeira
        if any(".Trash" in f for f in untracked):
            console.print("[red]❌ FALHA: Git está vendo a Lixeira (.Trash)![/red]")
            all_good = False
        else:
            console.print("[green]✅ Git Ignore: Lixeira invisível.[/green]")

        # Teste de Venv
        if any("agno_env" in f for f in untracked) or any(".venv" in f for f in untracked):
            console.print("[red]❌ FALHA: Git está vendo o ambiente virtual![/red]")
            all_good = False
        else:
            console.print("[green]✅ Git Ignore: Ambientes virtuais protegidos.[/green]")

        # Teste de Obsidian
        # Queremos que ele veja configs, mas NÃO workspace
        ignored_obsidian = repo.ignored(".obsidian/workspace")
        if ignored_obsidian:
            console.print("[green]✅ Git Ignore: Cache do Obsidian ignorado corretamente.[/green]")
        else:
            console.print("[yellow]⚠️  Aviso: O Git pode estar vendo arquivos temporários do Obsidian.[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Erro no Git: {e}[/red]")

    if all_good:
        console.print("\n[bold green]🎉 T002 APROVADA: Ambiente Pronto e Seguro.[/bold green]")
    else:
        console.print("\n[bold red]💥 T002 FALHOU: Verifique os erros acima.[/bold red]")


if __name__ == "__main__":
    run_audit()
