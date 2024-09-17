#
# Copyright (C) 2024 CESNET z.s.p.o.
#
# rdm-lang-tools is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see LICENSE file for more
# details.
#
import subprocess
import sys
import threading
from io import StringIO


def dump_stream(in_stream, out_stream):
    while True:
        buf = in_stream.readline()
        if not buf:
            break
        buf = buf.decode("utf-8")
        out_stream.write(buf)
        out_stream.flush()


def check_call(*args, **kwargs):
    print()
    process = subprocess.Popen(
        *args,
        **kwargs,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )

    ot = threading.Thread(
        target=dump_stream, args=(process.stdout, sys.stdout), daemon=True
    )
    ot.start()
    et = threading.Thread(
        target=dump_stream, args=(process.stderr, sys.stderr), daemon=True
    )
    et.start()
    process.wait()
    ot.join()
    et.join()
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, process.args)


def check_output(*args, **kwargs):
    process = subprocess.Popen(
        *args, **kwargs, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stream = StringIO()
    ot = threading.Thread(
        target=dump_stream, args=(process.stdout, stream), daemon=True
    )
    ot.start()
    et = threading.Thread(
        target=dump_stream, args=(process.stderr, sys.stderr), daemon=True
    )
    et.start()
    process.wait()
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, process.args)
    return stream.getvalue()
