{ ************************************************************************** }
{                                                                            }
{ nsh_render                                                                 }
{                                                                            }
{ Copyright © 2026 Yuriy Pisarev (ypisareff@outlook.com)                     }
{                                                                            }
{ ************************************************************************** }

unit nsh_render;

{$mode objfpc}{$H+}

interface

uses
  nsh_surface;

type
  TMat4 = array[0..15] of Single;

const
  SHADE_CONTOURS = 0;
  SHADE_COLOR    = 1;
  SHADE_BOTH     = 2;

type
  TDrawCam = record
    UseEye     : Boolean;
    Ex, Ey, Ez : Double;
    Dx, Dy, Dz : Double;
    Az, El     : Double;
    Dist       : Double;
    Fov        : Double;
  end;

function  RndInit(out Error: AnsiString): Boolean;

function  RndUpload(const S: TSurface; Zmid, Zspan: Double; out Error: AnsiString): Boolean;

procedure RndObstacles(const Rects: array of LongInt);

procedure RndShading(Mode: LongInt; Step: Double);

procedure RndDissolve(On: Boolean);

function  RndDraw(W, H: LongInt; const Cam: TDrawCam;
  PanX, PanY, BoxX, BoxY, BoxZ, Fill, LightAz, LightEl: Double; Fit, Grid, Axes: Boolean;
  out Error: AnsiString): Boolean;
procedure RndFree;

implementation

uses
  SysUtils, Math, GL, GLext, nsh_text, nsh_ticks;

const
  NL = #10;

const
  RAMP_SRC = 'vec3 ramp(float t) {' + NL +
    '  vec3 a = vec3(0.13, 0.18, 0.52);' + NL +
    '  vec3 b = vec3(0.10, 0.68, 0.56);' + NL +
    '  vec3 c = vec3(0.98, 0.86, 0.30);' + NL +
    '  return t < 0.5 ? mix(a, b, smoothstep(0.0, 1.0, t * 2.0))' + NL +
    '                 : mix(b, c, smoothstep(0.0, 1.0, (t - 0.5) * 2.0));' + NL +
    '}' + NL;
  CONT_SRC = 'uniform int uShade;' + NL +
    'uniform vec3 uCont;' + NL +
    'float contNum(float t) {' + NL +
    '  return (uCont.x + t * uCont.y) / uCont.z;' + NL +
    '}' + NL +
    'vec3 contInk(vec3 base, float f, float fw) {' + NL +
    '  float d  = abs(fract(f + 0.5) - 0.5) / max(fw, 1E-6);' + NL +
    '  float mn = 1.0 - smoothstep(0.30, 0.95, d);' + NL +
    '  float d5 = abs(fract(f * 0.2 + 0.5) - 0.5) * 5.0 / max(fw, 1E-6);' + NL +
    '  float mj = 1.0 - smoothstep(0.45, 1.25, d5);' + NL +
    '  float vis = (1.0 - smoothstep(0.40, 1.10, fw)) * smoothstep(0.004, 0.02, fw);' + NL +
    '  float a = clamp(mn * 0.55 + mj * 0.45, 0.0, 1.0) * vis;' + NL +
    '  return mix(base, vec3(0.07, 0.11, 0.17), a);' + NL +
    '}' + NL;
  BG_SRC = 'vec3 bgAt(vec2 uv) {' + NL +
    '  vec3 top = vec3(0.070, 0.092, 0.128);' + NL +
    '  vec3 bot = vec3(0.026, 0.035, 0.052);' + NL +
    '  vec3 c = mix(bot, top, smoothstep(0.0, 1.0, uv.y));' + NL +
    '  vec2 d = uv - 0.5;' + NL +
    '  c *= 1.0 - 0.55 * dot(d, d);' + NL +
    '  return c;' + NL +
    '}' + NL;
  VERT_SRC = '#version 330 core' + NL +
    'layout(location = 0) in vec3 aPos;' + NL +
    'layout(location = 1) in vec3 aNrm;' + NL +
    'uniform mat4 uMVP;' + NL +
    'uniform vec3 uScale;' + NL +
    'uniform vec3 uNrmScale;' + NL +
    'out vec3 vNrm;' + NL +
    'out vec3 vPos;' + NL +
    'out float vH;' + NL +
    'void main() {' + NL +
    '  gl_Position = uMVP * vec4(aPos, 1.0);' + NL +
    '  vNrm = normalize(aNrm * uNrmScale);' + NL +
    '  vPos = aPos * uScale;' + NL +
    '  vH = aPos.z;' + NL +
    '}' + NL;
  FRAG_SRC = '#version 330 core' + NL +
    'in vec3 vNrm;' + NL +
    'in vec3 vPos;' + NL +
    'in float vH;' + NL +
    'uniform vec3 uLight;' + NL +
    'uniform vec3 uEye;' + NL +
    'uniform vec3 uScale;' + NL +
    'out vec4 fColor;' + NL +
    'uniform vec2 uViewport;' + NL +
    'uniform vec2 uMeshHalf;' + NL +
    RAMP_SRC +
    CONT_SRC +
    BG_SRC +
    'void main() {' + NL +
    '  vec3 n = normalize(vNrm);' + NL +
    '  vec3 l = normalize(uLight);' + NL +
    '  vec3 v = normalize(uEye - vPos);' + NL +
    '  if (dot(n, v) < 0.0) { n = -n; l.z = -l.z; }' + NL +
    '  vec3 h = normalize(l + v);' + NL +
    '  float d = max(dot(n, l), 0.0);' + NL +
    '  float w = d * 0.75 + 0.25;' + NL +
    '  float sp = pow(max(dot(n, h), 0.0), 42.0);' + NL +
    '  float rim = pow(1.0 - max(dot(n, v), 0.0), 3.0);' + NL +
    '  vec3 base = (uShade == 0) ? vec3(0.80, 0.83, 0.86)' + NL +
    '                            : ramp(clamp((vH + 1.0) * 0.5, 0.0, 1.0));' + NL +
    '  float spk = (uShade == 0) ? 0.13 : 0.30;' + NL +
    '  vec3 col = base * (0.20 + 0.80 * w);' + NL +
    '  col += vec3(0.95, 0.98, 1.00) * sp * spk;' + NL +
    '  col += vec3(0.35, 0.62, 0.80) * rim * 0.16;' + NL +
    '  if (uShade != 1) {' + NL +
    '    float f = contNum(vH);' + NL +
    '    col = contInk(col, f, fwidth(f));' + NL +
    '  }' + NL +
    '  if (uMeshHalf.y > 0.0) {' + NL +
    '    vec2 o = uEye.xy;' + NL +
    '    vec2 dir = vPos.xy - o;' + NL +
    '    float t = 1.0E30;' + NL +
    '    if (abs(dir.x) > 1.0E-9) {' + NL +
    '      float bx = (dir.x > 0.0) ? uMeshHalf.x : -uMeshHalf.x;' + NL +
    '      t = min(t, (bx - o.x) / dir.x);' + NL +
    '    }' + NL +
    '    if (abs(dir.y) > 1.0E-9) {' + NL +
    '      float by = (dir.y > 0.0) ? uMeshHalf.y : -uMeshHalf.y;' + NL +
    '      t = min(t, (by - o.y) / dir.y);' + NL +
    '    }' + NL +
    '    float r = max(t - 1.0, 0.0);' + NL +
    '    float u = clamp(1.0 - r / 1.5, 0.0, 1.0);' + NL +
    '    float k = u * u * (3.0 - 2.0 * u);' + NL +
    '    col = mix(col, bgAt(gl_FragCoord.xy / uViewport), k);' + NL +
    '  }' + NL +
    '  fColor = vec4(col, 1.0);' + NL +
    '}' + NL;
  BG_VERT_SRC = '#version 330 core' + NL +
    'out vec2 vUv;' + NL +
    'void main() {' + NL +
    '  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);' + NL +
    '  vUv = p;' + NL +
    '  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);' + NL +
    '}' + NL;
  BG_FRAG_SRC = '#version 330 core' + NL +
    'in vec2 vUv;' + NL +
    'out vec4 fColor;' + NL +
    BG_SRC +
    'void main() {' + NL +
    '  fColor = vec4(bgAt(vUv), 1.0);' + NL +
    '}' + NL;

var
  FProg  : GLuint = 0;
  FVao   : GLuint = 0;
  FVbo   : GLuint = 0;
  FEbo   : GLuint = 0;
  FCount : GLsizei = 0;
  FGridEbo   : GLuint = 0;
  FGridCount : GLsizei = 0;
  FLocMVP   : GLint = -1;
  FLocLight : GLint = -1;
  FLocEye   : GLint = -1;
  FLocScale : GLint = -1;
  FLocNrmSc : GLint = -1;
  FLocShade : GLint = -1;
  FLocCont  : GLint = -1;
  FLocVp    : GLint = -1;
  FLocMeshH : GLint = -1;
  FBarShade : GLint = -1;
  FBarCont  : GLint = -1;
  FBgProg : GLuint = 0;
  FBgVao  : GLuint = 0;
  FLineProg : GLuint = 0;
  FLineVao  : GLuint = 0;
  FLineVbo  : GLuint = 0;
  FLineCnt  : GLsizei = 0;
  FLineMVP  : GLint = -1;
  FLineTint : GLint = -1;
  FBarProg : GLuint = 0;
  FBarVao  : GLuint = 0;
  FBarVbo  : GLuint = 0;
  FDomX0, FDomX1, FDomY0, FDomY1, FDomZ0, FDomZ1 : Double;
  FHalf  : Double = 1;
  FZspan : Double = 1;
  FZmid  : Double = 0;
  FShade : LongInt = SHADE_CONTOURS;
  FDissolve : Boolean = False;
  FCStep : Double = 0;
  FMeshX  : array of Single;
  FMeshY  : array of Single;
  FMeshZ  : array of Single;
  FMeshOk : array of Boolean;
  FSide   : LongInt = 0;

const
  BOX_XY = 1.0;
  BOX_Z  = 1.0;

const
  LINE_VERT_SRC = '#version 330 core' + NL +
    'layout(location = 0) in vec3 aPos;' + NL +
    'uniform mat4 uMVP;' + NL +
    'out float vDep;' + NL +
    'void main() {' + NL +
    '  vec4 p = uMVP * vec4(aPos, 1.0);' + NL +
    '  vDep = p.z / p.w;' + NL +
    '  gl_Position = p;' + NL +
    '}' + NL;
  LINE_FRAG_SRC = '#version 330 core' + NL +
    'in float vDep;' + NL +
    'uniform vec4 uTint;' + NL +
    'out vec4 fColor;' + NL +
    'void main() {' + NL +
    '  float t = clamp(vDep * 0.5 + 0.5, 0.0, 1.0);' + NL +
    '  float k = mix(1.0, 0.32, smoothstep(0.55, 1.0, t));' + NL +
    '  fColor = vec4(uTint.rgb * k, uTint.a);' + NL +
    '}' + NL;

const
  BAR_VERT_SRC = '#version 330 core' + NL +
    'layout(location = 0) in vec2 aPos;' + NL +
    'layout(location = 1) in float aT;' + NL +
    'out float vT;' + NL +
    'void main() {' + NL +
    '  vT = aT;' + NL +
    '  gl_Position = vec4(aPos, 0.0, 1.0);' + NL +
    '}' + NL;
  BAR_FRAG_SRC = '#version 330 core' + NL +
    'in float vT;' + NL +
    'out vec4 fColor;' + NL +
    RAMP_SRC +
    CONT_SRC +
    'void main() {' + NL +
    '  if (vT < 0.0) { fColor = vec4(0.62, 0.70, 0.82, 1.0); return; }' + NL +
    '  float t = clamp(vT, 0.0, 1.0);' + NL +
    '  vec3 col = (uShade == 0) ? vec3(0.80, 0.83, 0.86) : ramp(t);' + NL +
    '  if (uShade != 1) {' + NL +
    '    float f = contNum(t * 2.0 - 1.0);' + NL +
    '    col = contInk(col, f, fwidth(f));' + NL +
    '  }' + NL +
    '  fColor = vec4(col, 1.0);' + NL +
    '}' + NL;

procedure BuildAxes;
const
  DIV_COUNT = 5;
  TICK = 0.04;
var
  V : array of Single;
  N : LongInt;

  procedure Seg(X1, Y1, Z1, X2, Y2, Z2: Single);
  begin
    SetLength(V, N + 6);
    V[N + 0] := X1;
    V[N + 1] := Y1;
    V[N + 2] := Z1;
    V[N + 3] := X2;
    V[N + 4] := Y2;
    V[N + 5] := Z2;
    Inc(N, 6);
  end;

var
  I: LongInt;
  T: Single;
begin
  N := 0;
  Seg(-BOX_XY, -BOX_XY, -BOX_Z,  BOX_XY, -BOX_XY, -BOX_Z);
  Seg(BOX_XY, -BOX_XY, -BOX_Z,  BOX_XY,  BOX_XY, -BOX_Z);
  Seg(BOX_XY,  BOX_XY, -BOX_Z, -BOX_XY,  BOX_XY, -BOX_Z);
  Seg(-BOX_XY,  BOX_XY, -BOX_Z, -BOX_XY, -BOX_XY, -BOX_Z);
  Seg(-BOX_XY, -BOX_XY,  BOX_Z,  BOX_XY, -BOX_XY,  BOX_Z);
  Seg(BOX_XY, -BOX_XY,  BOX_Z,  BOX_XY,  BOX_XY,  BOX_Z);
  Seg(BOX_XY,  BOX_XY,  BOX_Z, -BOX_XY,  BOX_XY,  BOX_Z);
  Seg(-BOX_XY,  BOX_XY,  BOX_Z, -BOX_XY, -BOX_XY,  BOX_Z);
  Seg(-BOX_XY, -BOX_XY, -BOX_Z, -BOX_XY, -BOX_XY,  BOX_Z);
  Seg(BOX_XY, -BOX_XY, -BOX_Z,  BOX_XY, -BOX_XY,  BOX_Z);
  Seg(BOX_XY,  BOX_XY, -BOX_Z,  BOX_XY,  BOX_XY,  BOX_Z);
  Seg(-BOX_XY,  BOX_XY, -BOX_Z, -BOX_XY,  BOX_XY,  BOX_Z);
  for I := 1 to DIV_COUNT - 1 do
  begin
    T := -BOX_XY + 2 * BOX_XY * I / DIV_COUNT;
    Seg(T, -BOX_XY, -BOX_Z, T, -BOX_XY - TICK, -BOX_Z);
    Seg(-BOX_XY, T, -BOX_Z, -BOX_XY - TICK, T, -BOX_Z);
    T := -BOX_Z + 2 * BOX_Z * I / DIV_COUNT;
    Seg(-BOX_XY, -BOX_XY, T, -BOX_XY - TICK, -BOX_XY - TICK, T);
  end;
  if FLineVao = 0 then glGenVertexArrays(1, @FLineVao);
  if FLineVbo = 0 then glGenBuffers(1, @FLineVbo);
  glBindVertexArray(FLineVao);
  glBindBuffer(GL_ARRAY_BUFFER, FLineVbo);
  glBufferData(GL_ARRAY_BUFFER, N * SizeOf(Single), @V[0], GL_STATIC_DRAW);
  glEnableVertexAttribArray(0);
  glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * SizeOf(Single), Pointer(0));
  glBindVertexArray(0);
  FLineCnt := N div 3;
end;

function Compile(Kind: GLenum; const Src: AnsiString; out Error: AnsiString): GLuint;
var
  Status, Len: GLint;
  P: PAnsiChar;
  Log: AnsiString;
begin
  Result := glCreateShader(Kind);
  P := PAnsiChar(Src);
  glShaderSource(Result, 1, @P, nil);
  glCompileShader(Result);
  glGetShaderiv(Result, GL_COMPILE_STATUS, @Status);
  if Status = 0 then
  begin
    glGetShaderiv(Result, GL_INFO_LOG_LENGTH, @Len);
    if Len < 1 then Len := 1;
    SetLength(Log, Len);
    glGetShaderInfoLog(Result, Len, nil, PAnsiChar(Log));
    Error := 'shader did not compile: ' + Trim(Log);
    glDeleteShader(Result);
    Result := 0;
  end;
end;

function RndInit(out Error: AnsiString): Boolean;
var
  VS, FS: GLuint;
  Status, Len: GLint;
  Log: AnsiString;
begin
  Error := '';
  if FProg <> 0 then Exit(True);
  VS := Compile(GL_VERTEX_SHADER, VERT_SRC, Error);
  if VS = 0 then Exit(False);
  FS := Compile(GL_FRAGMENT_SHADER, FRAG_SRC, Error);
  if FS = 0 then
  begin
    glDeleteShader(VS); Exit(False);
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
    glGetProgramiv(FProg, GL_INFO_LOG_LENGTH, @Len);
    if Len < 1 then Len := 1;
    SetLength(Log, Len);
    glGetProgramInfoLog(FProg, Len, nil, PAnsiChar(Log));
    Error := 'program did not link: ' + Trim(Log);
    glDeleteProgram(FProg);
    FProg := 0;
    Exit(False);
  end;
  FLocMVP   := glGetUniformLocation(FProg, 'uMVP');
  FLocLight := glGetUniformLocation(FProg, 'uLight');
  FLocEye   := glGetUniformLocation(FProg, 'uEye');
  FLocScale := glGetUniformLocation(FProg, 'uScale');
  FLocNrmSc := glGetUniformLocation(FProg, 'uNrmScale');
  FLocShade := glGetUniformLocation(FProg, 'uShade');
  FLocCont  := glGetUniformLocation(FProg, 'uCont');
  FLocVp    := glGetUniformLocation(FProg, 'uViewport');
  FLocMeshH := glGetUniformLocation(FProg, 'uMeshHalf');
  VS := Compile(GL_VERTEX_SHADER, LINE_VERT_SRC, Error);
  if VS = 0 then Exit(False);
  FS := Compile(GL_FRAGMENT_SHADER, LINE_FRAG_SRC, Error);
  if FS = 0 then
  begin
    glDeleteShader(VS); Exit(False);
  end;
  FLineProg := glCreateProgram();
  glAttachShader(FLineProg, VS);
  glAttachShader(FLineProg, FS);
  glLinkProgram(FLineProg);
  glDeleteShader(VS);
  glDeleteShader(FS);
  glGetProgramiv(FLineProg, GL_LINK_STATUS, @Status);
  if Status = 0 then
  begin
    Error := 'line program did not link';
    glDeleteProgram(FLineProg);
    FLineProg := 0;
    Exit(False);
  end;
  FLineMVP := glGetUniformLocation(FLineProg, 'uMVP');
  FLineTint := glGetUniformLocation(FLineProg, 'uTint');
  VS := Compile(GL_VERTEX_SHADER, BAR_VERT_SRC, Error);
  if VS = 0 then Exit(False);
  FS := Compile(GL_FRAGMENT_SHADER, BAR_FRAG_SRC, Error);
  if FS = 0 then
  begin
    glDeleteShader(VS); Exit(False);
  end;
  FBarProg := glCreateProgram();
  glAttachShader(FBarProg, VS);
  glAttachShader(FBarProg, FS);
  glLinkProgram(FBarProg);
  glDeleteShader(VS);
  glDeleteShader(FS);
  glGetProgramiv(FBarProg, GL_LINK_STATUS, @Status);
  if Status = 0 then
  begin
    Error := 'color bar program did not link';
    glDeleteProgram(FBarProg);
    FBarProg := 0;
    Exit(False);
  end;
  FBarShade := glGetUniformLocation(FBarProg, 'uShade');
  FBarCont  := glGetUniformLocation(FBarProg, 'uCont');
  VS := Compile(GL_VERTEX_SHADER, BG_VERT_SRC, Error);
  if VS = 0 then Exit(False);
  FS := Compile(GL_FRAGMENT_SHADER, BG_FRAG_SRC, Error);
  if FS = 0 then
  begin
    glDeleteShader(VS); Exit(False);
  end;
  FBgProg := glCreateProgram();
  glAttachShader(FBgProg, VS);
  glAttachShader(FBgProg, FS);
  glLinkProgram(FBgProg);
  glDeleteShader(VS);
  glDeleteShader(FS);
  glGetProgramiv(FBgProg, GL_LINK_STATUS, @Status);
  if Status = 0 then
  begin
    Error := 'background program did not link';
    glDeleteProgram(FBgProg);
    FBgProg := 0;
    Exit(False);
  end;
  glGenVertexArrays(1, @FBgVao);
  BuildAxes;
  if not TxtInit(Error) then Exit(False);
  Result := True;
end;

function Finite3(const V: Single): Boolean; inline;
begin
  Result := (V = V) and (V > -1E30) and (V < 1E30);
end;

function RndUpload(const S: TSurface; Zmid, Zspan: Double; out Error: AnsiString): Boolean;
var
  Norm : array of TVertex;
  GridIdx : array of LongWord;
  I, J, A, GN, NSide, Step : LongInt;
  Cx, Cy, Half: Double;
begin
  Error := '';
  if (Length(S.Verts) = 0) or (Length(S.Idx) = 0) then
  begin
    Error := 'nothing to upload: the mesh is empty';
    Exit(False);
  end;
  Cx := (S.Verts[0].X + S.Verts[High(S.Verts)].X) / 2;
  Cy := (S.Verts[0].Y + S.Verts[High(S.Verts)].Y) / 2;
  Half := Max(Abs(S.Verts[High(S.Verts)].X - Cx), Abs(S.Verts[High(S.Verts)].Y - Cy));
  if Half < 1E-12 then Half := 1;
  if Zspan < 1E-12 then Zspan := 1;
  SetLength(Norm, Length(S.Verts));
  for I := 0 to High(S.Verts) do
  begin
    Norm[I] := S.Verts[I];
    Norm[I].X := (S.Verts[I].X - Cx) / Half;
    Norm[I].Y := (S.Verts[I].Y - Cy) / Half;
    Norm[I].Z := (S.Verts[I].Z - Zmid) / Zspan * 2;
  end;
  if FVao = 0 then glGenVertexArrays(1, @FVao);
  if FVbo = 0 then glGenBuffers(1, @FVbo);
  if FEbo = 0 then glGenBuffers(1, @FEbo);
  glBindVertexArray(FVao);
  glBindBuffer(GL_ARRAY_BUFFER, FVbo);
  glBufferData(GL_ARRAY_BUFFER, Length(Norm) * SizeOf(TVertex), @Norm[0], GL_STATIC_DRAW);
  glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, FEbo);
  glBufferData(GL_ELEMENT_ARRAY_BUFFER, Length(S.Idx) * SizeOf(LongWord), @S.Idx[0], GL_STATIC_DRAW);
  glEnableVertexAttribArray(0);
  glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, SizeOf(TVertex), Pointer(0));
  glEnableVertexAttribArray(1);
  glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, SizeOf(TVertex), Pointer(3 * SizeOf(Single)));
  glBindVertexArray(0);
  FSide := S.Side;
  SetLength(FMeshX, Length(Norm));
  SetLength(FMeshY, Length(Norm));
  SetLength(FMeshZ, Length(Norm));
  SetLength(FMeshOk, Length(Norm));
  for I := 0 to High(Norm) do
  begin
    FMeshX[I] := Norm[I].X;
    FMeshY[I] := Norm[I].Y;
    FMeshZ[I] := Norm[I].Z;
    FMeshOk[I] := Finite3(S.Verts[I].Z);
  end;
  FHalf := Half;
  FZspan := Zspan;
  FZmid := Zmid;
  FDomX0 := S.Verts[0].X;
  FDomX1 := S.Verts[High(S.Verts)].X;
  FDomY0 := S.Verts[0].Y;
  FDomY1 := S.Verts[High(S.Verts)].Y;
  FDomZ0 := Zmid - Zspan / 2;
  FDomZ1 := Zmid + Zspan / 2;
  SetLength(GridIdx, 0);
  NSide := S.Side;
  if NSide > 1 then
  begin
    Step := (NSide - 1) div 12;
    if Step < 1 then Step := 1;
    GN := 0;
    SetLength(GridIdx, NSide * NSide * 4);
    J := 0;
    while J < NSide do
    begin
      for I := 0 to NSide - 2 do
      begin
        A := J * NSide + I;
        if Finite3(S.Verts[A].Z) and Finite3(S.Verts[A + 1].Z) then
        begin
          GridIdx[GN] := A;
          GridIdx[GN + 1] := A + 1;
          Inc(GN, 2);
        end;
      end;
      Inc(J, Step);
    end;
    I := 0;
    while I < NSide do
    begin
      for J := 0 to NSide - 2 do
      begin
        A := J * NSide + I;
        if Finite3(S.Verts[A].Z) and Finite3(S.Verts[A + NSide].Z) then
        begin
          GridIdx[GN] := A;
          GridIdx[GN + 1] := A + NSide;
          Inc(GN, 2);
        end;
      end;
      Inc(I, Step);
    end;
    SetLength(GridIdx, GN);
  end;
  if FGridEbo = 0 then glGenBuffers(1, @FGridEbo);
  FGridCount := Length(GridIdx);
  if FGridCount > 0 then
  begin
    glBindVertexArray(FVao);
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, FGridEbo);
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, FGridCount * SizeOf(LongWord),
                 @GridIdx[0], GL_STATIC_DRAW);
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, FEbo);
    glBindVertexArray(0);
  end;
  FCount := Length(S.Idx);
  Result := True;
end;

procedure MatIdentity(out M: TMat4);
var I: Integer;
begin
  for I := 0 to 15 do M[I] := 0;
  M[0] := 1;
  M[5] := 1;
  M[10] := 1;
  M[15] := 1;
end;

procedure MatMul(const A, B: TMat4; out R: TMat4);
var I, J, K: Integer; S: Single;
begin
  for I := 0 to 3 do
    for J := 0 to 3 do
    begin
      S := 0;
      for K := 0 to 3 do S := S + A[K * 4 + J] * B[I * 4 + K];
      R[I * 4 + J] := S;
    end;
end;

procedure MatPerspective(out M: TMat4; Fov, Aspect, ZNear, ZFar: Double);
var F: Double;
begin
  MatIdentity(M);
  F := 1 / Tan(Fov / 2);
  M[0] := F / Aspect;
  M[5] := F;
  M[10] := (ZFar + ZNear) / (ZNear - ZFar);
  M[11] := -1;
  M[14] := (2 * ZFar * ZNear) / (ZNear - ZFar);
  M[15] := 0;
end;

procedure MatLookAt(out M: TMat4; Ex, Ey, Ez, Tx, Ty, Tz: Double);
var
  Fx, Fy, Fz, Rx, Ry, Rz, Ux, Uy, Uz, L: Double;
begin
  Fx := Tx - Ex;
  Fy := Ty - Ey;
  Fz := Tz - Ez;
  L := Sqrt(Fx * Fx + Fy * Fy + Fz * Fz);
  if L < 1E-12 then L := 1;
  Fx := Fx / L;
  Fy := Fy / L;
  Fz := Fz / L;
  Rx := Fy * 1 - Fz * 0;
  Ry := Fz * 0 - Fx * 1;
  Rz := 0;
  L := Sqrt(Rx * Rx + Ry * Ry + Rz * Rz);
  if L < 1E-12 then L := 1;
  Rx := Rx / L;
  Ry := Ry / L;
  Rz := Rz / L;
  Ux := Ry * Fz - Rz * Fy;
  Uy := Rz * Fx - Rx * Fz;
  Uz := Rx * Fy - Ry * Fx;
  MatIdentity(M);
  M[0] := Rx;
  M[4] := Ry;
  M[8]  := Rz;
  M[1] := Ux;
  M[5] := Uy;
  M[9]  := Uz;
  M[2] := -Fx;
  M[6] := -Fy;
  M[10] := -Fz;
  M[12] := -(Rx * Ex + Ry * Ey + Rz * Ez);
  M[13] := -(Ux * Ex + Uy * Ey + Uz * Ez);
  M[14] :=  (Fx * Ex + Fy * Ey + Fz * Ez);
end;

const
  MAX_LABELS = 96;

type
  TLabelBox = record X, Y, W, H: Double;
end;

var
  FObst      : array of LongInt;
  FLabelBox  : array[0..MAX_LABELS - 1] of TLabelBox;
  FLabelUsed : LongInt = 0;
  FMajor     : array of Single;
  FMajorCnt  : LongInt = 0;
  FMajorVbo  : GLuint = 0;
  FMajorVao  : GLuint = 0;

procedure RndDissolve(On: Boolean);
begin
  FDissolve := On;
end;

procedure RndShading(Mode: LongInt; Step: Double);
begin
  if (Mode < SHADE_CONTOURS) or (Mode > SHADE_BOTH) then Mode := SHADE_CONTOURS;
  FShade := Mode;
  if (Step > 0) and (Step < 1E30) and (Step = Step) then
    FCStep := Step
  else
    FCStep := 0;
end;

function ContourStep: Double;
begin
  if FCStep > 0 then Exit(FCStep);
  Result := NiceStep(FZspan / 15);
  if (Result <= 0) or (Result <> Result) or (Result > 1E30) then Result := 1;
end;

procedure RndObstacles(const Rects: array of LongInt);
var I: LongInt;
begin
  SetLength(FObst, Length(Rects));
  for I := 0 to High(Rects) do FObst[I] := Rects[I];
end;

function UnderPanel(Px, Py: Double): Boolean;
var I: LongInt;
begin
  Result := False;
  I := 0;
  while I + 3 < Length(FObst) do
  begin
    if (Px >= FObst[I]) and (Px <= FObst[I] + FObst[I + 2]) and
      (Py >= FObst[I + 1]) and (Py <= FObst[I + 1] + FObst[I + 3]) then
        Exit(True);
    Inc(I, 4);
  end;
end;

function BoxUnderPanel(BX, BY, BW, BH: Double): Boolean;
var I: LongInt;
begin
  Result := False;
  I := 0;
  while I + 3 < Length(FObst) do
  begin
    if (BX < FObst[I] + FObst[I + 2]) and (BX + BW > FObst[I]) and
      (BY < FObst[I + 1] + FObst[I + 3]) and (BY + BH > FObst[I + 1]) then
        Exit(True);
    Inc(I, 4);
  end;
end;

function BoxFree(BX, BY, BW, BH: Double): Boolean;
var I: LongInt;
begin
  Result := True;
  for I := 0 to FLabelUsed - 1 do
    if (BX < FLabelBox[I].X + FLabelBox[I].W) and (BX + BW > FLabelBox[I].X) and
      (BY < FLabelBox[I].Y + FLabelBox[I].H) and (BY + BH > FLabelBox[I].Y) then
        Exit(False);
end;

procedure BoxTake(BX, BY, BW, BH: Double);
begin
  if FLabelUsed >= MAX_LABELS then Exit;
  FLabelBox[FLabelUsed].X := BX;
  FLabelBox[FLabelUsed].Y := BY;
  FLabelBox[FLabelUsed].W := BW;
  FLabelBox[FLabelUsed].H := BH;
  Inc(FLabelUsed);
end;

function FracIndex(NVal: Double; AlongX: Boolean): Double;
var
  Lo, Hi, Mid: LongInt;
  A, B: Double;

  function Coord(K: LongInt): Double; inline;
  begin
    if AlongX then
      Coord := FMeshX[K]
    else
      Coord := FMeshY[K * FSide];
  end;

begin
  Result := 0;
  if FSide < 2 then Exit;
  if NVal <= Coord(0) then Exit;
  if NVal >= Coord(FSide - 1) then Exit(FSide - 1);
  Lo := 0;
  Hi := FSide - 1;
  while Hi - Lo > 1 do
  begin
    Mid := (Lo + Hi) div 2;
    if Coord(Mid) <= NVal then
      Lo := Mid
    else
      Hi := Mid;
  end;
  A := Coord(Lo);
  B := Coord(Hi);
  if B - A < 1E-12 then Exit(Lo);
  Result := Lo + (NVal - A) / (B - A);
end;

function MeshZAt(ColF: Double; Row: LongInt; out Z: Single): Boolean;
var
  C0, C1, A, B: LongInt;
  T: Double;
begin
  Result := False;
  if (FSide < 2) or (Row < 0) or (Row >= FSide) then Exit;
  if ColF < 0 then ColF := 0;
  if ColF > FSide - 1 then ColF := FSide - 1;
  C0 := Trunc(ColF);
  if C0 > FSide - 2 then C0 := FSide - 2;
  C1 := C0 + 1;
  T := ColF - C0;
  A := Row * FSide + C0;
  B := Row * FSide + C1;
  if (not FMeshOk[A]) or (not FMeshOk[B]) then Exit;
  Z := FMeshZ[A] * (1 - T) + FMeshZ[B] * T;
  Result := True;
end;

function MeshZAtCol(RowF: Double; Col: LongInt; out Z: Single): Boolean;
var
  R0, R1, A, B: LongInt;
  T: Double;
begin
  Result := False;
  if (FSide < 2) or (Col < 0) or (Col >= FSide) then Exit;
  if RowF < 0 then RowF := 0;
  if RowF > FSide - 1 then RowF := FSide - 1;
  R0 := Trunc(RowF);
  if R0 > FSide - 2 then R0 := FSide - 2;
  R1 := R0 + 1;
  T := RowF - R0;
  A := R0 * FSide + Col;
  B := R1 * FSide + Col;
  if (not FMeshOk[A]) or (not FMeshOk[B]) then Exit;
  Z := FMeshZ[A] * (1 - T) + FMeshZ[B] * T;
  Result := True;
end;

function Fmt(V: Double): AnsiString;
var
  A: Double;
begin
  if IsNan(V) then Exit('?');
  if IsInfinite(V) then
  begin
    if V > 0 then
      Exit('inf')
    else
      Exit('-inf')
  end;
  A := Abs(V);
  if A < 1E-10 then
    Result := '0'
  else if (A < 1E-3) or (A >= 1E5) then
  begin
    Result := AnsiString(FloatToStrF(V, ffExponent, 2, 0));
    Result := StringReplace(Result, 'E', 'e', [rfReplaceAll]);
    Result := StringReplace(Result, 'e+', 'e', [rfReplaceAll]);
    while Pos('e0', Result) > 0 do
      Result := StringReplace(Result, 'e0', 'e', [rfReplaceAll]);
    while Pos('e-0', Result) > 0 do
      Result := StringReplace(Result, 'e-0', 'e-', [rfReplaceAll]);
  end
  else
    Result := AnsiString(FloatToStrF(V, ffGeneral, 3, 0));
  Result := StringReplace(Result, ',', '.', [rfReplaceAll]);
end;

function BarRect(VpW, VpH: LongInt; out BX, BY, BW, BH, FullX, FullW: Double;
  out Right: Boolean): Boolean;
const
  BARW = 13;
  MRG  = 22;
  GAP  = 10;
  MINH = 90;
var
  LabW, WantH: Double;
  I, K, Side: LongInt;
  X0, X1: Double;
  BestH, BestY: array[0..1] of Double;
  Cut: array of Double;
  Y, GapY, GapH: Double;
  Blocked: Boolean;

begin
  Result := False;
  if (VpW < 220) or (VpH < 160) then Exit;
  if FDomZ1 - FDomZ0 <= 0 then Exit;
  BW := BARW;
  LabW := CELL_W * 8 + 12;
  FullW := BW + LabW + 8;
  WantH := VpH * 0.42;
  if WantH > 260 then WantH := 260;
  for Side := 0 to 1 do
  begin
    BestH[Side] := 0;
    BestY[Side] := 0;
    if Side = 0 then
    begin
      X0 := MRG - 2;
      X1 := X0 + FullW;
    end
                else begin
                  X1 := VpW - MRG + 2;
                  X0 := X1 - FullW;
                end;
    SetLength(Cut, 0);
    I := 0;
    while I + 3 < Length(FObst) do
    begin
      if (X0 < FObst[I] + FObst[I + 2]) and (X1 > FObst[I]) then
      begin
        K := Length(Cut);
        SetLength(Cut, K + 2);
        Cut[K] := FObst[I + 1] - GAP;
        Cut[K + 1] := FObst[I + 1] + FObst[I + 3] + GAP;
      end;
      Inc(I, 4);
    end;
    Y := 8;
    while Y < VpH - 8 do
    begin
      Blocked := False;
      K := 0;
      while K + 1 < Length(Cut) do
      begin
        if (Y >= Cut[K]) and (Y < Cut[K + 1]) then
        begin
          Y := Cut[K + 1];
          Blocked := True;
          Break;
        end;
        Inc(K, 2);
      end;
      if Blocked then Continue;
      GapY := Y;
      GapH := VpH - 8 - Y;
      K := 0;
      while K + 1 < Length(Cut) do
      begin
        if (Cut[K] > Y) and (Cut[K] - Y < GapH) then GapH := Cut[K] - Y;
        Inc(K, 2);
      end;
      if GapH > BestH[Side] then
      begin
        BestH[Side] := GapH;
        BestY[Side] := GapY;
      end;
      Y := GapY + GapH + 1;
    end;
  end;
  if BestH[1] > BestH[0] + 1 then
    Side := 1
  else
    Side := 0;
  Right := Side = 1;
  BH := BestH[Side] - 16;
  if BH > WantH then BH := WantH;
  if BH < MINH then Exit;
  BY := BestY[Side] + (BestH[Side] - BH) / 2;
  if Right then
  begin
    BX := VpW - MRG - BW;
    FullX := BX - LabW;
  end
  else begin
    BX := MRG;
    FullX := BX - 2;
  end;
  Result := True;
end;

procedure PutGridLabels(const MVP: TMat4; VpW, VpH: LongInt);
var
  BBX, BBY, BBW, BBH, BFX, BFW: Double;
  BRight: Boolean;
  Cx, Cy, Half, StepX, StepY: Double;
  PxPerX, PxPerY: Double;
  Fam, Idx, K: LongInt;
  GN: LongInt;

  function ToScreen(PX, PY, PZ: Double; out OX, OY: Double): Boolean;
  var A, B, Wc: Double;
  begin
    Result := False;
    A  := MVP[0] * PX + MVP[4] * PY + MVP[8]  * PZ + MVP[12];
    B  := MVP[1] * PX + MVP[5] * PY + MVP[9]  * PZ + MVP[13];
    Wc := MVP[3] * PX + MVP[7] * PY + MVP[11] * PZ + MVP[15];
    if Wc <= 1E-6 then Exit;
    OX := (A / Wc * 0.5 + 0.5) * VpW;
    OY := (1 - (B / Wc * 0.5 + 0.5)) * VpH;
    Result := True;
  end;

  function PixelsPerUnit(AlongX: Boolean): Double;
  var X0, Y0, X1, Y1, Wid: Double;
  begin
    Result := 0;
    if AlongX then
    begin
      Wid := FDomX1 - FDomX0;
      if Wid < 1E-12 then Exit;
      if not ToScreen((FDomX0 - Cx) / Half, 0, 0, X0, Y0) then Exit;
      if not ToScreen((FDomX1 - Cx) / Half, 0, 0, X1, Y1) then Exit;
    end
    else begin
      Wid := FDomY1 - FDomY0;
      if Wid < 1E-12 then Exit;
      if not ToScreen(0, (FDomY0 - Cy) / Half, 0, X0, Y0) then Exit;
      if not ToScreen(0, (FDomY1 - Cy) / Half, 0, X1, Y1) then Exit;
    end;
    Result := Sqrt(Sqr(X1 - X0) + Sqr(Y1 - Y0)) / Wid;
  end;

  procedure MajorSeg(AX, AY, AZ, BX, BY, BZ: Single);
  begin
    if GN + 6 > Length(FMajor) then SetLength(FMajor, 1024 + Length(FMajor) * 2);
    FMajor[GN] := AX;
    FMajor[GN+1] := AY;
    FMajor[GN+2] := AZ;
    FMajor[GN+3] := BX;
    FMajor[GN+4] := BY;
    FMajor[GN+5] := BZ;
    Inc(GN, 6);
  end;

  procedure OneLine(AlongX: Boolean; Value: Double);
  var
    ColF, NFix, NVar, PrevNVar: Double;
    Row: LongInt;
    Z, PrevZ: Single;
    Sx, Sy, Edge, BestEdge, BX, BY, BNVar: Double;
    HavePrev, Found: Boolean;
    AnchZ: Single;
    Txt: AnsiString;
    LW, LH, LX, LY: Double;
  begin
    if AlongX then
      NFix := (Value - Cx) / Half
              else
                NFix := (Value - Cy) / Half;
    ColF := FracIndex(NFix, AlongX);
    HavePrev := False;
    Found := False;
    BestEdge := 1E30;
    BX := 0;
    BY := 0;
    BNVar := 0;
    PrevNVar := 0;
    PrevZ := 0;
    AnchZ := 0;
    for Row := 0 to FSide - 1 do
    begin
      if AlongX then
      begin
        if not MeshZAt(ColF, Row, Z) then
        begin
          HavePrev := False;
          Continue;
        end;
        NVar := FMeshY[Row * FSide];
      end
      else begin
        if not MeshZAtCol(ColF, Row, Z) then
        begin
          HavePrev := False;
          Continue;
        end;
        NVar := FMeshX[Row];
      end;
      if HavePrev then
      begin
        if AlongX then
          MajorSeg(NFix, PrevNVar, PrevZ, NFix, NVar, Z)
                  else
                    MajorSeg(PrevNVar, NFix, PrevZ, NVar, NFix, Z);
      end;
      PrevNVar := NVar;
      PrevZ := Z;
      HavePrev := True;
      if AlongX then
      begin
        if not ToScreen(NFix, NVar, Z, Sx, Sy) then Continue;
      end
      else begin
        if not ToScreen(NVar, NFix, Z, Sx, Sy) then Continue;
      end;
      if (Sx < 0) or (Sx > VpW) or (Sy < 0) or (Sy > VpH) then Continue;
      if UnderPanel(Sx, Sy) then Continue;
      Edge := Sx;
      if VpW - Sx < Edge then Edge := VpW - Sx;
      if Sy < Edge then Edge := Sy;
      if VpH - Sy < Edge then Edge := VpH - Sy;
      if Edge < BestEdge then
      begin
        BestEdge := Edge;
        BX := Sx;
        BY := Sy;
        BNVar := NVar;
        AnchZ := Z;
        Found := True;
      end;
    end;
    if not Found then Exit;
    if AlongX then
      Txt := 'x=' + Fmt(Value)
    else
      Txt := 'y=' + Fmt(Value);
    LW := CELL_W * Length(Txt) + 8;
    LH := CELL_H + 10;
    LX := BX + 7;
    LY := BY - LH / 2;
    if LX + LW > VpW then LX := BX - 7 - LW;
    if LX < 0 then Exit;
    if LY < 2 then LY := 2;
    if LY + LH > VpH - 2 then LY := VpH - 2 - LH;
    if (LY < 2) or (LY + LH > VpH - 2) then Exit;
    if BoxUnderPanel(LX, LY, LW, LH) then Exit;
    if not BoxFree(LX, LY, LW, LH) then Exit;
    BoxTake(LX, LY, LW, LH);
    if AlongX then
      TxtAdd(Txt, NFix, BNVar, AnchZ, LX - BX, -(LY - BY) - LH)
              else
                TxtAdd(Txt, BNVar, NFix, AnchZ, LX - BX, -(LY - BY) - LH);
  end;

begin
  TxtClear;
  FLabelUsed := 0;
  if BarRect(VpW, VpH, BBX, BBY, BBW, BBH, BFX, BFW, BRight) then
    BoxTake(BFX, BBY - 16, BFW, BBH + 32);
  GN := 0;
  FMajorCnt := 0;
  if FSide < 2 then Exit;
  Cx := (FDomX0 + FDomX1) / 2;
  Cy := (FDomY0 + FDomY1) / 2;
  Half := FHalf;
  if Half < 1E-12 then Half := 1;
  PxPerX := PixelsPerUnit(True);
  PxPerY := PixelsPerUnit(False);
  if (PxPerX < 1E-6) or (PxPerY < 1E-6) then Exit;
  StepX := NiceStep(100 / PxPerX);
  StepY := NiceStep(100 / PxPerY);
  while (FDomX1 - FDomX0) / StepX > 12 do StepX := StepUp(StepX);
  while (FDomY1 - FDomY0) / StepY > 12 do StepY := StepUp(StepY);
  for Fam := 0 to 1 do
  begin
    if Fam = 0 then
    begin
      Idx := Ceil(FDomX0 / StepX);
      K := 0;
      while (Idx * StepX <= FDomX1) and (K < 64) do
      begin
        OneLine(True, Idx * StepX);
        Inc(Idx); Inc(K);
      end;
    end
    else begin
      Idx := Ceil(FDomY0 / StepY);
      K := 0;
      while (Idx * StepY <= FDomY1) and (K < 64) do
      begin
        OneLine(False, Idx * StepY);
        Inc(Idx); Inc(K);
      end;
    end;
  end;
  FMajorCnt := GN;
end;

procedure PutLabels(const MVP: TMat4; VpW, VpH: LongInt);
const
  DIV_COUNT = 5;
var
  I: LongInt;
  T, V: Double;
  Sx: AnsiString;
  EdgeY, EdgeX, CornX, CornY: Double;
  BestY, BestX: Double;
  LastX, LastY: array[0..1] of Double;
  LastOk: array[0..1] of Boolean;

  procedure Project(X, Y, Z: Double; out NX, NY: Double);
  var
    Cx, Cy, Cw: Double;
  begin
    Cx := MVP[0] * X + MVP[4] * Y + MVP[8]  * Z + MVP[12];
    Cy := MVP[1] * X + MVP[5] * Y + MVP[9]  * Z + MVP[13];
    Cw := MVP[3] * X + MVP[7] * Y + MVP[11] * Z + MVP[15];
    if Abs(Cw) < 1E-9 then Cw := 1E-9;
    NX := Cx / Cw;
    NY := Cy / Cw;
  end;

  function MidNdcY(X, Y: Double): Double;
  var A, B: Double;
  begin
    Project(X, Y, -BOX_Z, A, B);
    Result := B;
  end;

  function CornerNdcX(X, Y: Double): Double;
  var A, B: Double;
  begin
    Project(X, Y, 0, A, B);
    Result := A;
  end;

  function KeepTick(Axis, Idx: LongInt; X, Y: Double; Chars: LongInt): Boolean;
  var
    A, B, Px, Py, NeedX, NeedY: Double;
  begin
    Project(X, Y, -BOX_Z, A, B);
    Px := (A * 0.5 + 0.5) * VpW;
    Py := (1 - (B * 0.5 + 0.5)) * VpH;
    if (Idx = 0) or (Idx = DIV_COUNT) then
    begin
      LastX[Axis] := Px;
      LastY[Axis] := Py;
      LastOk[Axis] := True;
      Exit(True);
    end;
    if not LastOk[Axis] then
    begin
      LastX[Axis] := Px;
      LastY[Axis] := Py;
      LastOk[Axis] := True;
      Exit(True);
    end;
    NeedX := CELL_W * (Chars + 1);
    NeedY := CELL_H * 1.4;
    Result := (Abs(Px - LastX[Axis]) >= NeedX) or (Abs(Py - LastY[Axis]) >= NeedY);
    if Result then
    begin
      LastX[Axis] := Px;
      LastY[Axis] := Py;
    end;
  end;

begin
  TxtClear;
  LastOk[0] := False;
  LastOk[1] := False;
  LastX[0] := 0;
  LastY[0] := 0;
  LastX[1] := 0;
  LastY[1] := 0;
  if MidNdcY(0, -BOX_XY) <= MidNdcY(0, BOX_XY) then
    EdgeY := -BOX_XY
  else
    EdgeY := BOX_XY;
  if MidNdcY(-BOX_XY, 0) <= MidNdcY(BOX_XY, 0) then
    EdgeX := -BOX_XY
  else
    EdgeX := BOX_XY;
  BestX := 1E30;
  CornX := -BOX_XY;
  CornY := -BOX_XY;
  for I := 0 to 3 do
  begin
    V := CornerNdcX(BOX_XY * (1 - 2 * (I and 1)), BOX_XY * (1 - 2 * ((I shr 1) and 1)));
    if V < BestX then
    begin
      BestX := V;
      CornX := BOX_XY * (1 - 2 * (I and 1));
      CornY := BOX_XY * (1 - 2 * ((I shr 1) and 1));
    end;
  end;
  BestY := 0;
  for I := 0 to DIV_COUNT do
  begin
    T := -BOX_XY + 2 * BOX_XY * I / DIV_COUNT;
    V := FDomX0 + (FDomX1 - FDomX0) * I / DIV_COUNT;
    Sx := Fmt(V);
    if KeepTick(0, I, T, EdgeY, Length(Sx)) then
      TxtAdd(Sx, T, EdgeY, -BOX_Z, -CELL_W * Length(Sx) / 2, -CELL_H - 5);
    V := FDomY0 + (FDomY1 - FDomY0) * I / DIV_COUNT;
    Sx := Fmt(V);
    if KeepTick(1, I, EdgeX, T, Length(Sx)) then
      TxtAdd(Sx, EdgeX, T, -BOX_Z, -CELL_W * Length(Sx) / 2, -CELL_H - 5);
  end;
  for I := 0 to 2 do
  begin
    V := FDomZ0 + (FDomZ1 - FDomZ0) * I / 2;
    Sx := Fmt(V);
    TxtAdd(Sx, CornX, CornY, -BOX_Z + 2 * BOX_Z * I / 2, -CELL_W * Length(Sx) - 10, -CELL_H / 2);
  end;
  TxtAdd('x', BOX_XY * 1.18, EdgeY, -BOX_Z, -CELL_W / 2, -CELL_H - 5);
  TxtAdd('y', EdgeX, BOX_XY * 1.18, -BOX_Z, -CELL_W / 2, -CELL_H - 5);
  TxtAdd('z', CornX, CornY, BOX_Z * 1.35, -CELL_W - 12, -CELL_H / 2);
end;

procedure PutColorBar(VpW, VpH: LongInt);
const
  FR = 1;
var
  V: array of Single;
  N: LongInt;
  BX, BY, BW, BH, FullX, FullW: Double;
  Right: Boolean;
  Step, T, Zv, Frac: Double;
  Ticks, K: LongInt;
  Sx: AnsiString;
  Id: TMat4;

  procedure Quad(X0, Y0, X1, Y1, T0, T1: Double);
    procedure Vert(Px, Py, Tv: Double);
    begin
      if N + 3 > Length(V) then SetLength(V, (N + 3) * 2);
      V[N] := 2 * Px / VpW - 1;
      V[N + 1] := 1 - 2 * Py / VpH;
      V[N + 2] := Tv;
      Inc(N, 3);
    end;
  begin
    Vert(X0, Y1, T0); Vert(X1, Y1, T0); Vert(X1, Y0, T1);
    Vert(X0, Y1, T0); Vert(X1, Y0, T1); Vert(X0, Y0, T1);
  end;

begin
  if not BarRect(VpW, VpH, BX, BY, BW, BH, FullX, FullW, Right) then Exit;
  N := 0;
  SetLength(V, 128);
  Quad(BX - FR, BY - FR, BX + BW + FR, BY + BH + FR, -1, -1);
  Quad(BX, BY, BX + BW, BY + BH, 0, 1);
  if FBarProg <> 0 then
  begin
    if FBarVao = 0 then glGenVertexArrays(1, @FBarVao);
    if FBarVbo = 0 then glGenBuffers(1, @FBarVbo);
    glBindVertexArray(FBarVao);
    glBindBuffer(GL_ARRAY_BUFFER, FBarVbo);
    glBufferData(GL_ARRAY_BUFFER, N * SizeOf(Single), @V[0], GL_DYNAMIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 3 * SizeOf(Single), Pointer(0));
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 1, GL_FLOAT, GL_FALSE, 3 * SizeOf(Single),
                          Pointer(2 * SizeOf(Single)));
    glUseProgram(FBarProg);
    glUniform1i(FBarShade, FShade);
    glUniform3f(FBarCont, FZmid, FZspan / 2, ContourStep);
    glDrawArrays(GL_TRIANGLES, 0, N div 3);
    glBindVertexArray(0);
  end;
  Step := NiceStep((FDomZ1 - FDomZ0) / 3);
  if Step <= 0 then Exit;
  Ticks := 0;
  MatIdentity(Id);
  TxtClear;
  K := Floor(FDomZ0 / Step);
  while K * Step <= FDomZ1 + Abs(Step) * 1E-9 do
  begin
    Zv := K * Step;
    Inc(K);
    Frac := (Zv - FDomZ0) / (FDomZ1 - FDomZ0);
    if (Frac < -0.001) or (Frac > 1.001) then Continue;
    Sx := Fmt(Zv);
    T := BY + BH * (1 - Frac);
    if Right then
      TxtAdd(Sx, 2 * (BX - 7) / VpW - 1, 1 - 2 * T / VpH, 0,
             -CELL_W * Length(Sx), -CELL_H / 2)
    else
      TxtAdd(Sx, 2 * (BX + BW + 7) / VpW - 1, 1 - 2 * T / VpH, 0, 0, -CELL_H / 2);
    Inc(Ticks);
  end;
  TxtAdd('z', 2 * (BX + BW / 2) / VpW - 1, 1 - 2 * BY / VpH, 0, -CELL_W / 2, 12);
  if Ticks > 0 then TxtFlush(Id[0], VpW, VpH);
end;

function RndDraw(W, H: LongInt; const Cam: TDrawCam;
  PanX, PanY, BoxX, BoxY, BoxZ, Fill, LightAz, LightEl: Double; Fit, Grid, Axes: Boolean;
  out Error: AnsiString): Boolean;
var
  Proj, View, Scale, VP, MVP: TMat4;
  Ex, Ey, Ez, Lx, Ly, Lz: Double;
  Tx, Ty, Tz, Rx, Ry, Ux, Uy, Uz, L: Double;
  Ax, Ay, Az_, El, Dist, Fov: Double;
  Pass: LongInt;
  Need: Double;
  Hy, Rad: Double;

begin
  Error := '';
  if (FProg = 0) or (FVao = 0) or (FCount = 0) then
  begin
    Error := 'nothing to draw: upload a mesh first';
    Exit(False);
  end;
  Fov := Cam.Fov;
  if Cam.UseEye then
  begin
    Ex := Cam.Ex;
    Ey := Cam.Ey;
    Ez := Cam.Ez;
    Az_ := ArcTan2(-Cam.Dy, -Cam.Dx);
    L := Sqrt(Cam.Dx * Cam.Dx + Cam.Dy * Cam.Dy + Cam.Dz * Cam.Dz);
    if L < 1E-300 then L := 1;
    El := ArcSin(Max(-1, Min(1, -Cam.Dz / L)));
    Ax := Ex + Cam.Dx / L;
    Ay := Ey + Cam.Dy / L;
    Dist := 1;
  end
  else begin
    Az_ := Cam.Az;
    El := Cam.El;
    Dist := Cam.Dist;
    Ex := Dist * Cos(El) * Cos(Az_);
    Ey := Dist * Cos(El) * Sin(Az_);
    Ez := Dist * Sin(El);
    Ax := 0;
    Ay := 0;
  end;
  Rx := -Sin(Az_);
  Ry := Cos(Az_);
  Ux := -Sin(El) * Cos(Az_);
  Uy := -Sin(El) * Sin(Az_);
  Uz := Cos(El);
  L := Sqrt(Ux * Ux + Uy * Uy + Uz * Uz);
  if L < 1E-12 then L := 1;
  Ux := Ux / L;
  Uy := Uy / L;
  Uz := Uz / L;
  Tx := Rx * PanX + Ux * PanY;
  Ty := Ry * PanX + Uy * PanY;
  Tz :=            Uz * PanY;
  if BoxX <= 0 then BoxX := 1;
  if BoxY <= 0 then BoxY := 1;
  if BoxZ <= 0 then BoxZ := 1;
  MatIdentity(Scale);
  Scale[0] := BoxX;
  Scale[5] := BoxY;
  Scale[10] := BoxZ;
  if Cam.UseEye then
    MatPerspective(Proj, Fov, W / H, 0.002, 400)
                else
                  MatPerspective(Proj, Fov, W / H, 0.05, 100);
  if Cam.UseEye then
    MatLookAt(View, Ex + Tx, Ey + Ty, Ez + Tz,
              Ax + Tx, Ay + Ty, Ez + Cam.Dz / L + Tz)
  else
    MatLookAt(View, Ex + Tx, Ey + Ty, Ez + Tz, Tx, Ty, Tz);
  MatMul(Proj, View, VP);
  MatMul(VP, Scale, MVP);
  if Fit then
  begin
    Rad := Sqrt(BoxX * BoxX + BoxY * BoxY + BoxZ * BoxZ);
    if Rad > Dist * 0.98 then Rad := Dist * 0.98;
    Hy := Tan(ArcSin(Rad / Dist)) / Tan(Fov / 2);
    if Hy < 1E-9 then Hy := 1E-9;
    if Fill <= 0 then Fill := 1;
    Need := Fill / Hy;
    for Pass := 0 to 3 do
    begin
      MVP[Pass * 4 + 0] := Need * MVP[Pass * 4 + 0];
      MVP[Pass * 4 + 1] := Need * MVP[Pass * 4 + 1];
    end;
  end;
  Lx := Cos(LightEl) * Cos(LightAz);
  Ly := Cos(LightEl) * Sin(LightAz);
  Lz := Sin(LightEl);
  glViewport(0, 0, W, H);
  glClearColor(0.026, 0.035, 0.052, 1.0);
  glClear(GL_COLOR_BUFFER_BIT or GL_DEPTH_BUFFER_BIT);
  if FBgProg <> 0 then
  begin
    glDisable(GL_DEPTH_TEST);
    glUseProgram(FBgProg);
    glBindVertexArray(FBgVao);
    glDrawArrays(GL_TRIANGLES, 0, 3);
    glBindVertexArray(0);
  end;
  glEnable(GL_DEPTH_TEST);
  glUseProgram(FProg);
  glUniformMatrix4fv(FLocMVP, 1, GL_FALSE, @MVP[0]);
  glUniform3f(FLocLight, Lx, Ly, Lz);
  glUniform3f(FLocEye, Ex + Tx, Ey + Ty, Ez + Tz);
  glUniform3f(FLocScale, BoxX, BoxY, BoxZ);
  if FHalf < 1E-12 then FHalf := 1;
  if FZspan < 1E-12 then FZspan := 1;
  glUniform3f(FLocNrmSc, FHalf / BoxX, FHalf / BoxY, FZspan / (2 * BoxZ));
  glUniform1i(FLocShade, FShade);
  glUniform2f(FLocVp, W, H);
  if FDissolve then
    glUniform2f(FLocMeshH,
                (FDomX1 - FDomX0) / (2 * FHalf) * BoxX,
                (FDomY1 - FDomY0) / (2 * FHalf) * BoxY)
  else
    glUniform2f(FLocMeshH, 0, 0);
  glUniform3f(FLocCont, FZmid, FZspan / 2, ContourStep);
  glEnable(GL_POLYGON_OFFSET_FILL);
  glPolygonOffset(1.0, 1.0);
  glBindVertexArray(FVao);
  glDrawElements(GL_TRIANGLES, FCount, GL_UNSIGNED_INT, nil);
  glDisable(GL_POLYGON_OFFSET_FILL);
  if Grid and (FGridCount > 0) and (FLineProg <> 0) then
  begin
    glUseProgram(FLineProg);
    glUniformMatrix4fv(FLineMVP, 1, GL_FALSE, @MVP[0]);
    glUniform4f(FLineTint, 0.85, 0.93, 1.00, 1.0);
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, FGridEbo);
    glEnable(GL_BLEND);
    glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ZERO, GL_ONE);
    glUniform4f(FLineTint, 0.85, 0.93, 1.00, 0.30);
    glDrawElements(GL_LINES, FGridCount, GL_UNSIGNED_INT, nil);
    glDisable(GL_BLEND);
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, FEbo);
  end;
  glBindVertexArray(0);
  if Axes and (FLineProg <> 0) and (FLineCnt > 0) then
  begin
    glUseProgram(FLineProg);
    glUniformMatrix4fv(FLineMVP, 1, GL_FALSE, @MVP[0]);
    glUniform4f(FLineTint, 0.62, 0.70, 0.82, 1.0);
    glBindVertexArray(FLineVao);
    glDrawArrays(GL_LINES, 0, FLineCnt);
    glBindVertexArray(0);
    glDisable(GL_DEPTH_TEST);
    PutLabels(MVP, W, H);
    TxtFlush(MVP[0], W, H);
    glEnable(GL_DEPTH_TEST);
  end
  else if Grid then
  begin
    PutGridLabels(MVP, W, H);
    if (FMajorCnt > 0) and (FLineProg <> 0) then
    begin
      if FMajorVao = 0 then glGenVertexArrays(1, @FMajorVao);
      if FMajorVbo = 0 then glGenBuffers(1, @FMajorVbo);
      glBindVertexArray(FMajorVao);
      glBindBuffer(GL_ARRAY_BUFFER, FMajorVbo);
      glBufferData(GL_ARRAY_BUFFER, FMajorCnt * SizeOf(Single), @FMajor[0], GL_DYNAMIC_DRAW);
      glEnableVertexAttribArray(0);
      glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * SizeOf(Single), Pointer(0));
      glUseProgram(FLineProg);
      glUniformMatrix4fv(FLineMVP, 1, GL_FALSE, @MVP[0]);
      glUniform4f(FLineTint, 0.95, 0.98, 1.00, 0.75);
      glEnable(GL_BLEND);
      glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ZERO, GL_ONE);
      glDrawArrays(GL_LINES, 0, FMajorCnt div 3);
      glDisable(GL_BLEND);
      glBindVertexArray(0);
    end;
    glDisable(GL_DEPTH_TEST);
    TxtFlush(MVP[0], W, H);
    PutColorBar(W, H);
    glEnable(GL_DEPTH_TEST);
  end;
  glFinish();
  Result := True;
end;

procedure RndFree;
begin
  if FEbo <> 0 then
  begin
    glDeleteBuffers(1, @FEbo);
    FEbo := 0;
    if FBarVbo <> 0 then
    begin
      glDeleteBuffers(1, @FBarVbo);
      FBarVbo := 0;
    end;
  if FBarVao <> 0 then
  begin
    glDeleteVertexArrays(1, @FBarVao);
    FBarVao := 0;
  end;
  if FBarProg <> 0 then
  begin
    glDeleteProgram(FBarProg);
    FBarProg := 0;
  end;
end;
  if FGridEbo <> 0 then
  begin
    glDeleteBuffers(1, @FGridEbo);
    FGridEbo := 0;
  end;
  if FVbo <> 0 then
  begin
    glDeleteBuffers(1, @FVbo);
    FVbo := 0;
  end;
  TxtFree;
  if FLineVbo <> 0 then
  begin
    glDeleteBuffers(1, @FLineVbo);
    FLineVbo := 0;
  end;
  if FLineVao <> 0 then
  begin
    glDeleteVertexArrays(1, @FLineVao);
    FLineVao := 0;
  end;
  if FLineProg <> 0 then
  begin
    glDeleteProgram(FLineProg);
    FLineProg := 0;
  end;
  if FVao <> 0 then
  begin
    glDeleteVertexArrays(1, @FVao);
    FVao := 0;
  end;
  if FProg <> 0 then
  begin
    glDeleteProgram(FProg);
    FProg := 0;
  end;
  FCount := 0;
  FGridCount := 0;
end;

end.
