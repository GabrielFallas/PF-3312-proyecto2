"""
common/timer.py
===============
Primitivas de medicion de tiempo de alta resolucion.

Se usa time.perf_counter() porque es monotono y de la mayor resolucion
disponible en la plataforma, lo que lo hace adecuado para medir latencias
de orden de milisegundos sin verse afectado por ajustes del reloj del SO.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class LatencySample:
    """Resultado de una unica ejecucion cronometrada.

    Attributes
    ----------
    total_s        : latencia total de extremo a extremo (segundos).
    ttft_s         : Time To First Token / primer byte util (segundos).
                     Solo aplica a generacion en streaming (LLM/TTS); None si
                     la operacion no es incremental.
    ok             : True si la ejecucion concluyo sin excepcion.
    error          : mensaje de error (si ok es False).
    extra          : metricas adicionales especificas del servicio
                     (p.ej. tokens generados, tokens/seg, RTF, WER).
    """
    total_s: float = 0.0
    ttft_s: float | None = None
    ok: bool = True
    error: str = ""
    extra: dict = field(default_factory=dict)


class StreamTimer:
    """Cronometro para operaciones en streaming.

    Captura el TTFT (tiempo hasta el primer fragmento recibido) y la
    latencia total. Uso tipico::

        t = StreamTimer()
        t.start()
        for chunk in stream:
            t.mark_first_token()   # idempotente: solo registra el primero
            ...
        sample = t.stop(extra={"tokens": n})
    """

    def __init__(self) -> None:
        self._t0: float | None = None
        self._t_first: float | None = None

    def start(self) -> None:
        self._t0 = time.perf_counter()
        self._t_first = None

    def mark_first_token(self) -> None:
        if self._t_first is None:
            self._t_first = time.perf_counter()

    def stop(self, extra: dict | None = None) -> LatencySample:
        if self._t0 is None:
            raise RuntimeError("StreamTimer.stop() llamado antes de start().")
        end = time.perf_counter()
        ttft = (self._t_first - self._t0) if self._t_first is not None else None
        return LatencySample(
            total_s=end - self._t0,
            ttft_s=ttft,
            extra=extra or {},
        )


@contextmanager
def measure():
    """Context manager para cronometrar bloques no incrementales (STT batch).

    Devuelve una lista de un elemento donde, al salir, queda la latencia::

        with measure() as elapsed:
            do_work()
        print(elapsed[0])   # segundos
    """
    box = [0.0]
    t0 = time.perf_counter()
    try:
        yield box
    finally:
        box[0] = time.perf_counter() - t0
