"""Convert YuE2's native Vocal ABC voice to timing-equivalent rests."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class InstrumentalAbcResult:
    abc: str
    muted_notes: int
    vocal_lines: int


_VOICE = re.compile(r"^\s*V:\s*([^\s]+)")
_FIELD = re.compile(r"^\s*[A-Za-z]:")


def _duration(line: str, start: int) -> tuple[str, int]:
    end = start
    while end < len(line) and (line[end].isdigit() or line[end] == "/"):
        end += 1
    return line[start:end], end


def _quoted(line: str, start: int, delimiter: str) -> tuple[str, int]:
    end = line.find(delimiter, start + 1)
    if end < 0:
        return line[start:], len(line)
    return line[start : end + 1], end + 1


def _mute_music_line(line: str) -> tuple[str, int]:
    output: list[str] = []
    muted = 0
    index = 0
    while index < len(line):
        char = line[index]
        if char == "%":
            output.append(line[index:])
            break
        if char in {'"', "!", "+"}:
            token, index = _quoted(line, index, char)
            output.append(token)
            continue
        if char == "{":
            end = line.find("}", index + 1)
            index = len(line) if end < 0 else end + 1
            continue
        if char == "[":
            end = line.find("]", index + 1)
            if end < 0:
                output.append(char)
                index += 1
                continue
            content = line[index + 1 : end]
            if re.match(r"\s*[A-Za-z]:", content):
                output.append(line[index : end + 1])
                index = end + 1
                continue
            duration, next_index = _duration(line, end + 1)
            while next_index < len(line) and line[next_index] == "-":
                next_index += 1
            output.append("z" + duration)
            muted += 1
            index = next_index
            continue
        note_start = index
        while index < len(line) and line[index] in "^_=":
            index += 1
        if index < len(line) and line[index] in "ABCDEFGabcdefg":
            index += 1
            while index < len(line) and line[index] in "',":
                index += 1
            duration, index = _duration(line, index)
            while index < len(line) and line[index] == "-":
                index += 1
            output.append("z" + duration)
            muted += 1
            continue
        index = note_start
        if char == "-":
            index += 1
            continue
        output.append(char)
        index += 1
    return "".join(output), muted


def mute_vocal_abc(abc: str) -> InstrumentalAbcResult:
    """Mute music lines in native ``V: Vocal`` blocks without changing duration."""
    lines = abc.splitlines(keepends=True)
    output: list[str] = []
    in_vocal = False
    saw_vocal = False
    muted_notes = 0
    vocal_lines = 0

    for line in lines:
        body = line.rstrip("\r\n")
        ending = line[len(body) :]
        voice = _VOICE.match(body)
        if voice:
            in_vocal = voice.group(1).casefold() == "vocal"
            saw_vocal = saw_vocal or in_vocal
            output.append(line)
            continue
        if not in_vocal or not body.strip() or body.lstrip().startswith("%") or _FIELD.match(body):
            output.append(line)
            continue
        muted_line, count = _mute_music_line(body)
        output.append(muted_line + ending)
        if count:
            muted_notes += count
            vocal_lines += 1

    if not saw_vocal or not vocal_lines:
        raise ValueError("no native Vocal blocks found in YuE2 ABC plan")
    return InstrumentalAbcResult("".join(output), muted_notes, vocal_lines)
