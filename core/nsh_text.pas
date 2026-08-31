{ ************************************************************************** }
{                                                                            }
{ nsh_text                                                                   }
{                                                                            }
{ Copyright © 2026 Yuriy Pisarev (ypisareff@outlook.com)                     }
{                                                                            }
{ ************************************************************************** }

unit nsh_text;

{$mode objfpc}{$H+}

interface

type
  TTextVertex = packed record
    AX, AY, AZ : Single;
    OX, OY     : Single;
    U, V       : Single;
  end;

function  TxtInit(out Error: AnsiString): Boolean;
procedure TxtClear;
procedure TxtAdd(const Text: AnsiString; WX, WY, WZ: Single; PxX, PxY: Single);
function  TxtFlush(const MVP; W, H: LongInt): Boolean;
procedure TxtFree;

const
  GLYPH_W = 5;
  GLYPH_H = 7;
  GLYPH_N = 17;
  CELL_W  = 6;
  CELL_H  = 9;

implementation

uses
  SysUtils, GL, GLext;

const
  NL = #10;
  NSH_GL_R8  = $8229;
  NSH_GL_RED = $1903;
  FONT: array[0..GLYPH_N - 1, 0..GLYPH_H - 1] of Byte = (
    (%01110, %10001, %10011, %10101, %11001, %10001, %01110),
    (%00100, %01100, %00100, %00100, %00100, %00100, %01110),
    (%01110, %10001, %00001, %00010, %00100, %01000, %11111),
    (%11111, %00010, %00100, %00010, %00001, %10001, %01110),
    (%00010, %00110, %01010, %10010, %11111, %00010, %00010),
    (%11111, %10000, %11110, %00001, %00001, %10001, %01110),
    (%00110, %01000, %10000, %11110, %10001, %10001, %01110),
    (%11111, %00001, %00010, %00100, %01000, %01000, %01000),
    (%01110, %10001, %10001, %01110, %10001, %10001, %01110),
    (%01110, %10001, %10001, %01111, %00001, %00010, %01100),
    (%00000, %00000, %00000, %11111, %00000, %00000, %00000),
    (%00000, %00000, %00000, %00000, %00000, %01100, %01100),
    (%00000, %00000, %01110, %10001, %11111, %10000, %01110),
    (%00000, %00000, %10001, %01010, %00100, %01010, %10001),
    (%00000, %00000, %10001, %10001, %01111, %00001, %01110),
    (%00000, %00000, %11111, %00010, %00100, %01000, %11111),
    (%00000, %00000, %11111, %00000, %11111, %00000, %00000)
  );
  TEXT_VERT_SRC = '#version 330 core' + NL +
    'layout(location = 0) in vec3 aAnchor;' + NL +
    'layout(location = 1) in vec2 aOffset;' + NL +
    'layout(location = 2) in vec2 aUV;' + NL +
    'uniform mat4 uMVP;' + NL +
    'uniform vec2 uPxToNdc;' + NL +
    'out vec2 vUV;' + NL +
    'void main() {' + NL +
    '  vec4 p = uMVP * vec4(aAnchor, 1.0);' + NL +
    '  p /= p.w;' + NL +
    '  vec2 sc = floor(p.xy / uPxToNdc + 0.5) + floor(aOffset + 0.5);' + NL +
    '  gl_Position = vec4(sc * uPxToNdc, p.z, 1.0);' + NL +
    '  vUV = aUV;' + NL +
    '}' + NL;
  TEXT_FRAG_SRC = '#version 330 core' + NL +
    'in vec2 vUV;' + NL +
    'uniform sampler2D uFont;' + NL +
    'out vec4 fColor;' + NL +
    'void main() {' + NL +
    '  float a = texture(uFont, vUV).r;' + NL +
    '  if (a < 0.5) discard;' + NL +
    '  fColor = vec4(0.85, 0.88, 0.94, 1.0);' + NL +
    '}' + NL;

var
  FProg : GLuint = 0;
  FTex  : GLuint = 0;
  FVao  : GLuint = 0;
  FVbo  : GLuint = 0;
  FMVP  : GLint = -1;
  FPx   : GLint = -1;
  FFont : GLint = -1;
  FData : array of TTextVertex;
  FUsed : LongInt = 0;

function GlyphOf(C: AnsiChar): LongInt;
begin
  case C of
    '0'..'9' : Result := Ord(C) - Ord('0');
    '-'      : Result := 10;
    '.', ',' : Result := 11;
    '='      : Result := 16;
    'e', 'E' : Result := 12;
    'x', 'X' : Result := 13;
    'y', 'Y' : Result := 14;
    'z', 'Z' : Result := 15;
  else
    Result := -1;
  end;
end;

function Compile(Kind: GLenum; const Src: AnsiString; out Error: AnsiString): GLuint;
var
  Status: GLint;
begin
  Result := glCreateShader(Kind);
  glShaderSource(Result, 1, @Src[1], nil);
  glCompileShader(Result);
  glGetShaderiv(Result, GL_COMPILE_STATUS, @Status);
  if Status = 0 then
  begin
    Error := 'text shader did not compile';
    glDeleteShader(Result);
    Result := 0;
  end;
end;

function TxtInit(out Error: AnsiString): Boolean;
var
  VS, FS: GLuint;
  Status: GLint;
  Pix: array of Byte;
  G, Row, Col: LongInt;
  P: PAnsiChar;
  Src: AnsiString;
begin
  Error := '';
  if FProg <> 0 then Exit(True);
  Src := TEXT_VERT_SRC;
  P := PAnsiChar(Src);
  VS := glCreateShader(GL_VERTEX_SHADER);
  glShaderSource(VS, 1, @P, nil);
  glCompileShader(VS);
  glGetShaderiv(VS, GL_COMPILE_STATUS, @Status);
  if Status = 0 then
  begin
    Error := 'text vertex shader did not compile';
    Exit(False);
  end;
  Src := TEXT_FRAG_SRC;
  P := PAnsiChar(Src);
  FS := glCreateShader(GL_FRAGMENT_SHADER);
  glShaderSource(FS, 1, @P, nil);
  glCompileShader(FS);
  glGetShaderiv(FS, GL_COMPILE_STATUS, @Status);
  if Status = 0 then
  begin
    Error := 'text fragment shader did not compile';
    Exit(False);
  end;
  FProg := glCreateProgram();
  glAttachShader(FProg, VS);
  glAttachShader(FProg, FS);
  glLinkProgram(FProg);
  glDeleteShader(VS);
  glDeleteShader(FS);
  glGetProgramiv(FProg, GL_LINK_STATUS, @Status);
  if Status = 0 then
  begin
    Error := 'text program did not link';
    glDeleteProgram(FProg);
    FProg := 0;
    Exit(False);
  end;
  FMVP  := glGetUniformLocation(FProg, 'uMVP');
  FPx   := glGetUniformLocation(FProg, 'uPxToNdc');
  FFont := glGetUniformLocation(FProg, 'uFont');
  SetLength(Pix, GLYPH_N * GLYPH_W * GLYPH_H);
  for G := 0 to GLYPH_N - 1 do
    for Row := 0 to GLYPH_H - 1 do
      for Col := 0 to GLYPH_W - 1 do
        if (FONT[G, Row] shr (GLYPH_W - 1 - Col)) and 1 = 1 then
          Pix[Row * (GLYPH_N * GLYPH_W) + G * GLYPH_W + Col] := 255
        else
          Pix[Row * (GLYPH_N * GLYPH_W) + G * GLYPH_W + Col] := 0;
  glGenTextures(1, @FTex);
  glBindTexture(GL_TEXTURE_2D, FTex);
  glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
  glTexImage2D(GL_TEXTURE_2D, 0, NSH_GL_R8, GLYPH_N * GLYPH_W, GLYPH_H, 0,
               NSH_GL_RED, GL_UNSIGNED_BYTE, @Pix[0]);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
  glGenVertexArrays(1, @FVao);
  glGenBuffers(1, @FVbo);
  glBindVertexArray(FVao);
  glBindBuffer(GL_ARRAY_BUFFER, FVbo);
  glEnableVertexAttribArray(0);
  glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, SizeOf(TTextVertex), Pointer(0));
  glEnableVertexAttribArray(1);
  glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, SizeOf(TTextVertex), Pointer(3 * SizeOf(Single)));
  glEnableVertexAttribArray(2);
  glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, SizeOf(TTextVertex), Pointer(5 * SizeOf(Single)));
  glBindVertexArray(0);
  Result := True;
end;

procedure TxtClear;
begin
  FUsed := 0;
end;

procedure Push(WX, WY, WZ, OX, OY, U, V: Single);
begin
  if FUsed >= Length(FData) then SetLength(FData, 256 + Length(FData) * 2);
  FData[FUsed].AX := WX;
  FData[FUsed].AY := WY;
  FData[FUsed].AZ := WZ;
  FData[FUsed].OX := OX;
  FData[FUsed].OY := OY;
  FData[FUsed].U  := U;
  FData[FUsed].V  := V;
  Inc(FUsed);
end;

procedure TxtAdd(const Text: AnsiString; WX, WY, WZ, PxX, PxY: Single);
var
  I, G: LongInt;
  X0, U0, U1: Single;
begin
  X0 := PxX;
  for I := 1 to Length(Text) do
  begin
    G := GlyphOf(Text[I]);
    if G >= 0 then
    begin
      U0 := G / GLYPH_N;
      U1 := (G + 1) / GLYPH_N;
      Push(WX, WY, WZ, X0,          PxY,          U0, 1);
      Push(WX, WY, WZ, X0 + CELL_W, PxY,          U1, 1);
      Push(WX, WY, WZ, X0,          PxY + CELL_H, U0, 0);
      Push(WX, WY, WZ, X0 + CELL_W, PxY,          U1, 1);
      Push(WX, WY, WZ, X0 + CELL_W, PxY + CELL_H, U1, 0);
      Push(WX, WY, WZ, X0,          PxY + CELL_H, U0, 0);
    end;
    X0 := X0 + CELL_W;
  end;
end;

function TxtFlush(const MVP; W, H: LongInt): Boolean;
begin
  Result := True;
  if (FProg = 0) or (FUsed = 0) then Exit;
  glUseProgram(FProg);
  glUniformMatrix4fv(FMVP, 1, GL_FALSE, @MVP);
  glUniform2f(FPx, 2 / W, 2 / H);
  glActiveTexture(GL_TEXTURE0);
  glBindTexture(GL_TEXTURE_2D, FTex);
  glUniform1i(FFont, 0);
  glBindVertexArray(FVao);
  glBindBuffer(GL_ARRAY_BUFFER, FVbo);
  glBufferData(GL_ARRAY_BUFFER, FUsed * SizeOf(TTextVertex), @FData[0], GL_DYNAMIC_DRAW);
  glDrawArrays(GL_TRIANGLES, 0, FUsed);
  glBindVertexArray(0);
end;

procedure TxtFree;
begin
  if FVbo <> 0 then
  begin
    glDeleteBuffers(1, @FVbo);
    FVbo := 0;
  end;
  if FVao <> 0 then
  begin
    glDeleteVertexArrays(1, @FVao);
    FVao := 0;
  end;
  if FTex <> 0 then
  begin
    glDeleteTextures(1, @FTex);
    FTex := 0;
  end;
  if FProg <> 0 then
  begin
    glDeleteProgram(FProg);
    FProg := 0;
  end;
  FData := nil;
  FUsed := 0;
end;

end.
