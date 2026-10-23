export class SageError extends Error {
  public readonly code: string;
  public readonly exitCode: number;

  constructor(message: string, code = "E_SAGE", exitCode = 1) {
    super(message);
    this.name = "SageError";
    this.code = code;
    this.exitCode = exitCode;
  }
}

export function toSageError(error: unknown): SageError {
  if (error instanceof SageError) return error;
  if (error instanceof Error) return new SageError(error.message, "E_INTERNAL", 1);
  return new SageError(String(error), "E_INTERNAL", 1);
}
