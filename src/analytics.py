import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None


class AnalyticsManager:
    """
    Registra el historial de videos generados y expone métricas agregadas.
    Los datos se almacenan en `stats_history.json`.
    """

    def __init__(self, stats_file: str = "stats_history.json"):
        self.stats_path = Path(stats_file)
        if not self.stats_path.exists():
            self.stats_path.write_text("[]", encoding="utf-8")
        logger.debug(f"AnalyticsManager iniciado en {self.stats_path.resolve()}")

    def _load_history(self) -> List[Dict]:
        try:
            with open(self.stats_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error("Historial de estadísticas corrupto. Reiniciando archivo.")
            self.stats_path.write_text("[]", encoding="utf-8")
            return []

    def _save_history(self, records: List[Dict]):
        with open(self.stats_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

    def log_generation(
        self,
        profile: str,
        topic: str,
        duration_minutes: float,
        upload_status: str,
    ):
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "profile": profile or "Sin Perfil",
            "topic": topic,
            "duration_minutes": float(duration_minutes),
            "upload_status": upload_status,
        }
        history = self._load_history()
        history.append(record)
        self._save_history(history)
        logger.info(f"📈 Registro agregado a stats: {record}")

    def get_history(self, limit: Optional[int] = None) -> List[Dict]:
        history = self._load_history()
        if limit is not None:
            return history[-limit:]
        return history

    def get_growth_data(self):
        history = self._load_history()
        if not history:
            return None

        if pd is None:
            logger.warning("Pandas no está instalado. Retornando datos crudos.")
            return history

        df = pd.DataFrame(history)
        df["duration_minutes"] = df["duration_minutes"].astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date
        df["hours_saved"] = df["duration_minutes"] * 60 / 60  # 1 min video = 60 min humanos => 1h ahorrada
        df["hours_saved"] = df["duration_minutes"]  # equivalencia: 1 min video = 1 hora humana

        summary = df.groupby("profile").agg(
            total_videos=("topic", "count"),
            total_minutes=("duration_minutes", "sum"),
            hours_saved=("hours_saved", "sum"),
        ).reset_index()
        summary["total_hours_video"] = summary["total_minutes"] / 60

        daily = df.groupby(["date", "profile"]).size().unstack(fill_value=0)
        return {
            "summary": summary,
            "daily": daily,
            "raw": df,
        }








