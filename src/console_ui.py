"""
Console UI: Interfaz visual mejorada para la terminal usando Rich.
Hace que los logs parezcan de una película de hackers.
"""

from rich.console import Console as RichConsole
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from typing import Dict, Any, Optional
import sys


class Console:
    """Clase estática para logs visuales mejorados con Rich."""
    
    _instance: Optional['Console'] = None
    _rich_console: Optional[RichConsole] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Console, cls).__new__(cls)
            cls._rich_console = RichConsole(
                width=120,
                force_terminal=True,
                color_system="auto"
            )
        return cls._instance
    
    @classmethod
    def log_step(cls, message: str, icon: str = "🚀"):
        """
        Muestra un mensaje de paso/proceso con icono y color.
        
        Args:
            message: Mensaje a mostrar
            icon: Icono a usar (por defecto 🚀)
        """
        if cls._rich_console is None:
            cls._instance = cls()
        
        text = Text()
        text.append(f"{icon} ", style="bold cyan")
        text.append(message, style="cyan")
        cls._rich_console.print(text)
    
    @classmethod
    def log_success(cls, message: str, icon: str = "✅"):
        """
        Muestra un mensaje de éxito en verde brillante.
        
        Args:
            message: Mensaje a mostrar
            icon: Icono a usar (por defecto ✅)
        """
        if cls._rich_console is None:
            cls._instance = cls()
        
        text = Text()
        text.append(f"{icon} ", style="bold green")
        text.append(message, style="bold green")
        cls._rich_console.print(text)
    
    @classmethod
    def log_error(cls, message: str, icon: str = "❌"):
        """
        Muestra un mensaje de error en rojo con panel de alerta.
        
        Args:
            message: Mensaje a mostrar
            icon: Icono a usar (por defecto ❌)
        """
        if cls._rich_console is None:
            cls._instance = cls()
        
        error_panel = Panel(
            f"{icon} {message}",
            border_style="red",
            title="[bold red]ERROR[/bold red]",
            title_align="left",
            padding=(1, 2)
        )
        cls._rich_console.print(error_panel)
    
    @classmethod
    def log_warning(cls, message: str, icon: str = "⚠️"):
        """
        Muestra un mensaje de advertencia en amarillo.
        
        Args:
            message: Mensaje a mostrar
            icon: Icono a usar (por defecto ⚠️)
        """
        if cls._rich_console is None:
            cls._instance = cls()
        
        text = Text()
        text.append(f"{icon} ", style="bold yellow")
        text.append(message, style="yellow")
        cls._rich_console.print(text)
    
    @classmethod
    def log_info(cls, message: str, icon: str = "ℹ️"):
        """
        Muestra un mensaje informativo.
        
        Args:
            message: Mensaje a mostrar
            icon: Icono a usar (por defecto ℹ️)
        """
        if cls._rich_console is None:
            cls._instance = cls()
        
        text = Text()
        text.append(f"{icon} ", style="bold blue")
        text.append(message, style="blue")
        cls._rich_console.print(text)
    
    @classmethod
    def print_stats(cls, stats_dict: Dict[str, Any], title: str = "📊 Estadísticas de Sesión"):
        """
        Muestra una tabla con estadísticas usando Rich Table.
        
        Args:
            stats_dict: Diccionario con las estadísticas
            title: Título de la tabla
        """
        if cls._rich_console is None:
            cls._instance = cls()
        
        table = Table(
            title=title,
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
            border_style="bright_blue"
        )
        
        table.add_column("Métrica", style="cyan", no_wrap=True)
        table.add_column("Valor", style="green", justify="right")
        
        for key, value in stats_dict.items():
            # Formatear el valor si es necesario
            if isinstance(value, (int, float)):
                if isinstance(value, float):
                    formatted_value = f"{value:.2f}"
                else:
                    formatted_value = str(value)
            else:
                formatted_value = str(value)
            
            table.add_row(key, formatted_value)
        
        cls._rich_console.print("\n")
        cls._rich_console.print(table)
        cls._rich_console.print("\n")
    
    @classmethod
    def print_panel(cls, message: str, title: str = "", style: str = "bold cyan", border_style: str = "cyan"):
        """
        Muestra un panel grande con un mensaje.
        
        Args:
            message: Mensaje a mostrar
            title: Título del panel
            style: Estilo del texto
            border_style: Estilo del borde
        """
        if cls._rich_console is None:
            cls._instance = cls()
        
        panel = Panel(
            message,
            title=title,
            title_align="center",
            border_style=border_style,
            style=style,
            padding=(1, 2),
            box=box.DOUBLE
        )
        cls._rich_console.print("\n")
        cls._rich_console.print(panel)
        cls._rich_console.print("\n")
    
    @classmethod
    def print_cronos_banner(cls):
        """
        Muestra el banner épico del "PROYECTO CRONOS" cuando se activa el bucle infinito.
        """
        if cls._rich_console is None:
            cls._instance = cls()
        
        banner_text = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║          ██████╗ ██████╗  ██████╗ ██╗   ██╗███████╗          ║
║          ██╔══██╗██╔══██╗██╔═══██╗╚██╗ ██╔╝██╔════╝          ║
║          ██████╔╝██████╔╝██║   ██║ ╚████╔╝ ███████╗          ║
║          ██╔══██╗██╔══██╗██║   ██║  ╚██╔╝  ╚════██║          ║
║          ██║  ██║██║  ██║╚██████╔╝   ██║   ███████║          ║
║          ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚══════╝          ║
║                                                               ║
║              ██████╗ ██████╗  ██████╗ ███╗   ██╗            ║
║              ██╔══██╗██╔══██╗██╔═══██╗████╗  ██║            ║
║              ██████╔╝██████╔╝██║   ██║██╔██╗ ██║            ║
║              ██╔══██╗██╔══██╗██║   ██║██║╚██╗██║            ║
║              ██║  ██║██║  ██║╚██████╔╝██║ ╚████║            ║
║              ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝            ║
║                                                               ║
║                    [bold green]PROYECTO CRONOS ACTIVO[/bold green]                    ║
║                                                               ║
║              [cyan]Modo Bucle Infinito Iniciado[/cyan]              ║
║          [yellow]Generación Automática de Videos Activada[/yellow]          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
        """
        
        panel = Panel(
            banner_text,
            border_style="bright_green",
            box=box.DOUBLE,
            padding=(1, 2)
        )
        
        cls._rich_console.print("\n" * 2)
        cls._rich_console.print(panel, justify="center")
        cls._rich_console.print("\n" * 2)
    
    @classmethod
    def print_separator(cls, char: str = "═", style: str = "cyan"):
        """
        Imprime una línea separadora.
        
        Args:
            char: Carácter a usar para la línea
            style: Estilo de color
        """
        if cls._rich_console is None:
            cls._instance = cls()
        
        cls._rich_console.print(char * 80, style=style)
    
    @classmethod
    def print_progress(cls, current: int, total: int, message: str = "Procesando"):
        """
        Muestra una barra de progreso simple.
        
        Args:
            current: Paso actual
            total: Total de pasos
            message: Mensaje a mostrar
        """
        if cls._rich_console is None:
            cls._instance = cls()
        
        percentage = (current / total) * 100 if total > 0 else 0
        bar_length = 40
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)
        
        progress_text = f"[cyan]{message}[/cyan] [green]{bar}[/green] [yellow]{current}/{total}[/yellow] [bold]{percentage:.1f}%[/bold]"
        cls._rich_console.print(progress_text)

