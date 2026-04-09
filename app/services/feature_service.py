"""Geracao de features estatisticas para monitoramento."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
from scipy.stats import linregress

from app.domain.mappings import NUMERIC_SIGNALS


class FeatureService:
    """Calcula features de tendencia e estabilidade por modo operacional."""

    def compute(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame

        features = frame.copy().sort_values("timestamp").reset_index(drop=True)
        features["mode_segment_id"] = (
            features["mode_key"].ne(features["mode_key"].shift()).cumsum()
        )

        candidate_signals = [
            signal for signal in NUMERIC_SIGNALS if signal in features.columns
        ]
        for extra_signal in ("delta_filtro_oleo_bar", "pv_vib_max_mils", "pv_temp_estator_max_c"):
            if extra_signal in features.columns and extra_signal not in candidate_signals:
                candidate_signals.append(extra_signal)

        for signal in candidate_signals:
            features = self._append_signal_features(features, signal)

        return features

    def _append_signal_features(self, frame: pd.DataFrame, signal: str) -> pd.DataFrame:
        for _, segment in frame.groupby("mode_segment_id", sort=False):
            segment_index = segment.index
            segment_series = (
                segment[["timestamp", signal]]
                .dropna(subset=["timestamp"])
                .set_index("timestamp")[signal]
                .astype(float)
                .sort_index()
            )

            if segment_series.empty:
                continue

            ma_5m = segment_series.rolling("5min", min_periods=1).mean()
            ma_15m = segment_series.rolling("15min", min_periods=1).mean()
            ma_1h = segment_series.rolling("60min", min_periods=1).mean()
            std_15m = segment_series.rolling("15min", min_periods=2).std()
            std_1h = segment_series.rolling("60min", min_periods=2).std()
            min_15m = segment_series.rolling("15min", min_periods=1).min()
            max_15m = segment_series.rolling("15min", min_periods=1).max()
            min_1h = segment_series.rolling("60min", min_periods=1).min()
            max_1h = segment_series.rolling("60min", min_periods=1).max()
            ewma = segment_series.ewm(span=15, adjust=False, min_periods=1).mean()
            zscore_1h = (segment_series - ma_1h) / std_1h.replace(0, np.nan)
            ewma_gap_abs = (segment_series - ewma).abs()
            slope_15m = self._compute_slopes(
                timestamps=segment_series.index.to_series(),
                values=segment_series,
                window=timedelta(minutes=15),
            )
            slope_1h = self._compute_slopes(
                timestamps=segment_series.index.to_series(),
                values=segment_series,
                window=timedelta(hours=1),
            )

            signal_features = {
                f"{signal}__ma_5m": ma_5m,
                f"{signal}__ma_15m": ma_15m,
                f"{signal}__ma_1h": ma_1h,
                f"{signal}__std_15m": std_15m,
                f"{signal}__std_1h": std_1h,
                f"{signal}__min_15m": min_15m,
                f"{signal}__max_15m": max_15m,
                f"{signal}__min_1h": min_1h,
                f"{signal}__max_1h": max_1h,
                f"{signal}__slope_15m": slope_15m,
                f"{signal}__slope_1h": slope_1h,
                f"{signal}__zscore_1h": zscore_1h,
                f"{signal}__ewma": ewma,
                f"{signal}__ewma_gap_abs": ewma_gap_abs,
            }

            for feature_name, series in signal_features.items():
                frame.loc[segment_index, feature_name] = series.to_numpy()

        return frame

    def _compute_slopes(
        self,
        timestamps: pd.Series,
        values: pd.Series,
        window: timedelta,
    ) -> pd.Series:
        numeric_values = values.astype(float).to_numpy()
        ts_seconds = timestamps.astype("int64").to_numpy() / 1_000_000_000
        output = np.full(len(numeric_values), np.nan)

        for idx in range(len(numeric_values)):
            window_start = ts_seconds[idx] - window.total_seconds()
            start_idx = int(np.searchsorted(ts_seconds, window_start, side="left"))

            x_window = ts_seconds[start_idx : idx + 1]
            y_window = numeric_values[start_idx : idx + 1]
            valid_mask = ~np.isnan(y_window)
            if valid_mask.sum() < 3:
                continue

            x_valid = (x_window[valid_mask] - x_window[valid_mask][0]) / 60.0
            y_valid = y_window[valid_mask]
            slope = linregress(x_valid, y_valid).slope
            output[idx] = slope

        return pd.Series(output, index=timestamps.index)
