import sys

class Parser:
    def __init__(self, filename):
        """Inicializa o parser e carrega os comandos do arquivo .vm."""
        with open(filename, "r") as file:
            self.commands = [
                line.split("//")[0].strip().split()  # Remove comentários e divide tokens
                for line in file.readlines()
                if line.strip() and not line.startswith("//")
            ]
        self.current_command = None

    def hasMoreCommands(self):
        """Retorna True se ainda há comandos a processar."""
        return bool(self.commands)

    def advance(self):
        """Lê o próximo comando e o define como corrente."""
        if self.hasMoreCommands():
            self.current_command = self.commands.pop(0)

    def commandType(self):
        """Retorna o tipo do comando."""
        if self.current_command[0] in {"add", "sub", "neg", "eq", "gt", "lt", "and", "or", "not"}:
            return "C_ARITHMETIC"
        elif self.current_command[0] == "push":
            return "C_PUSH"
        elif self.current_command[0] == "pop":
            return "C_POP"
        elif self.current_command[0] == "label":
            return "C_LABEL"
        elif self.current_command[0] == "goto":
            return "C_GOTO"
        elif self.current_command[0] == "if-goto":
            return "C_IF"
        elif self.current_command[0] == "function":
            return "C_FUNCTION"
        elif self.current_command[0] == "call":
            return "C_CALL"
        elif self.current_command[0] == "return":
            return "C_RETURN"
        else:
            raise ValueError(f"Comando desconhecido: {self.current_command[0]}")

    def arg1(self):
        """Retorna o primeiro argumento do comando."""
        if self.commandType() == "C_ARITHMETIC":
            return self.current_command[0]
        return self.current_command[1]

    def arg2(self):
        """Retorna o segundo argumento (apenas para Push, Pop, Function, Call)."""
        if self.commandType() in {"C_PUSH", "C_POP", "C_FUNCTION", "C_CALL"}:
            return int(self.current_command[2])
        raise ValueError(f"arg2 chamado para comando inválido: {self.current_command}")

class CodeWriter:
    def __init__(self, filename):
        """Inicializa o CodeWriter e define o arquivo de saída."""
        self.file = open(filename, "w")
        self.label_count = 0
        self.file_name = ""
        self.function_name = ""

    def setFileName(self, filename):
        """Atualiza o nome do arquivo atual para lidar com variáveis estáticas."""
        self.file_name = filename.split("/")[-1].replace(".vm", "")

    def writeArithmetic(self, command):
        """Escreve código assembly para comandos aritméticos."""
        if command in {"add", "sub", "and", "or"}:
            op = {"add": "+", "sub": "-", "and": "&", "or": "|"}[command]
            asm_code = "@SP\nAM=M-1\nD=M\nA=A-1\nM=M" + op + "D\n"
        elif command in {"neg", "not"}:
            op = {"neg": "-", "not": "!"}[command]
            asm_code = "@SP\nA=M-1\nM=" + op + "M\n"
        elif command in {"eq", "gt", "lt"}:
            jump = {"eq": "JEQ", "gt": "JGT", "lt": "JLT"}[command]
            label_true = f"TRUE_{self.label_count}"
            label_end = f"END_{self.label_count}"
            asm_code = (
                "@SP\nAM=M-1\nD=M\nA=A-1\nD=M-D\n"
                f"@{label_true}\nD;{jump}\n"
                "@SP\nA=M-1\nM=0\n"
                f"@{label_end}\n0;JMP\n"
                f"({label_true})\n@SP\nA=M-1\nM=-1\n"
                f"({label_end})\n"
            )
            self.label_count += 1
        else:
            raise ValueError(f"Comando aritmético inválido: {command}")

        self.file.write(asm_code)

    def writePush(self, segment, index):
        """Escreve código assembly para comando push."""
        segment_map = {
            "constant": f"@{index}\nD=A\n",
            "local": f"@LCL\nD=M\n@{index}\nA=D+A\nD=M\n",
            "argument": f"@ARG\nD=M\n@{index}\nA=D+A\nD=M\n",
            "this": f"@THIS\nD=M\n@{index}\nA=D+A\nD=M\n",
            "that": f"@THAT\nD=M\n@{index}\nA=D+A\nD=M\n",
            "temp": f"@{5 + index}\nD=M\n",
            "pointer": f"@{'THIS' if index == 0 else 'THAT'}\nD=M\n",
            "static": f"@{self.file_name}.{index}\nD=M\n"
        }

        if segment not in segment_map:
            raise ValueError(f"Segmento inválido: {segment}")

        asm_code = segment_map[segment] + "@SP\nA=M\nM=D\n@SP\nM=M+1\n"
        self.file.write(asm_code)

    def writePop(self, segment, index):
        """Escreve código assembly para comando pop."""
        if segment == "constant":
            raise ValueError("Pop não pode ser usado com constant.")

        segment_map = {
            "local": "@LCL",
            "argument": "@ARG",
            "this": "@THIS",
            "that": "@THAT",
            "temp": f"@{5 + index}",
            "pointer": "@THIS" if index == 0 else "@THAT",
            "static": f"@{self.file_name}.{index}"
        }

        if segment not in segment_map:
            raise ValueError(f"Segmento inválido: {segment}")

        if segment in {"temp", "pointer", "static"}:
            asm_code = "@SP\nAM=M-1\nD=M\n" + segment_map[segment] + "\nM=D\n"
        else:
            asm_code = (
                f"@{index}\nD=A\n"
                + segment_map[segment]
                + "\nD=M+D\n@R13\nM=D\n"
                "@SP\nAM=M-1\nD=M\n@R13\nA=M\nM=D\n"
            )

        self.file.write(asm_code)

    def writeLabel(self, label):
        """Escreve código para label."""
        self.file.write(f"({self.function_name}${label})\n")

    def writeGoto(self, label):
        """Escreve código para goto."""
        self.file.write(f"@{self.function_name}${label}\n0;JMP\n")

    def writeIf(self, label):
        """Escreve código para if-goto."""
        self.file.write("@SP\nAM=M-1\nD=M\n")
        self.file.write(f"@{self.function_name}${label}\nD;JNE\n")

    def writeCall(self, functionName, numArgs):
        """Escreve código para call functionName numArgs."""
        return_label = f"{functionName}$ret.{self.label_count}"
        self.label_count += 1
        self.file.write(
            f"@{return_label}\nD=A\n@SP\nA=M\nM=D\n@SP\nM=M+1\n"
            "@LCL\nD=M\n@SP\nA=M\nM=D\n@SP\nM=M+1\n"
            "@ARG\nD=M\n@SP\nA=M\nM=D\n@SP\nM=M+1\n"
            "@THIS\nD=M\n@SP\nA=M\nM=D\n@SP\nM=M+1\n"
            "@THAT\nD=M\n@SP\nA=M\nM=D\n@SP\nM=M+1\n"
            f"@{numArgs}\nD=A\n@5\nD=D+A\n@SP\nD=M-D\n@ARG\nM=D\n"
            "@SP\nD=M\n@LCL\nM=D\n"
            f"@{functionName}\n0;JMP\n"
            f"({return_label})\n"
        )

    def writeFunction(self, functionName, numLocals):
        """Escreve código para function functionName numLocals."""
        self.function_name = functionName
        self.file.write(f"({functionName})\n")
        for _ in range(numLocals):
            self.writePush("constant", 0)

    def writeReturn(self):
        """Escreve código para return."""
        self.file.write(
            "@LCL\nD=M\n@R13\nM=D\n"  # Salva LCL em R13 (FRAME = LCL)
            "@5\nA=D-A\nD=M\n@R14\nM=D\n"  # Guarda RET (endereço de retorno) em R14
            "@SP\nAM=M-1\nD=M\n@ARG\nA=M\nM=D\n"  # *ARG = pop()
            "@ARG\nD=M+1\n@SP\nM=D\n"  # SP = ARG + 1
            "@R13\nAM=M-1\nD=M\n@THAT\nM=D\n"  # THAT = *(FRAME - 1)
            "@R13\nAM=M-1\nD=M\n@THIS\nM=D\n"  # THIS = *(FRAME - 2)
            "@R13\nAM=M-1\nD=M\n@ARG\nM=D\n"  # ARG = *(FRAME - 3)
            "@R13\nD=M-1\nAM=D\nD=M\n@LCL\nM=D\n"  # LCL = *(FRAME - 4)  <-- CORREÇÃO AQUI
            "@R14\nA=M\n0;JMP\n"  # Goto RET (return address)
        )

    def writeInit(self):
        """Escreve código de inicialização (bootstrap)."""
        self.file.write("@256\nD=A\n@SP\nM=D\n")
        self.writeCall("Main.fibonacci", 1)

    def close(self):
        """Fecha o arquivo de saída."""
        self.file.close()

class VMTranslator:
    """Gerencia a tradução do arquivo .vm para .asm."""
    def __init__(self, input_file):
        self.parser = Parser(input_file)
        output_file = input_file.replace(".vm", ".asm")
        self.code_writer = CodeWriter(output_file)

    def translate(self):
        """Realiza a tradução completa do arquivo .vm para .asm."""
        self.code_writer.writeInit()  # Adiciona código de inicialização

        while self.parser.hasMoreCommands():
            self.parser.advance()
            command_type = self.parser.commandType()

            if command_type == "C_ARITHMETIC":
                self.code_writer.writeArithmetic(self.parser.arg1())
            elif command_type == "C_PUSH":
                self.code_writer.writePush(self.parser.arg1(), self.parser.arg2())
            elif command_type == "C_POP":
                self.code_writer.writePop(self.parser.arg1(), self.parser.arg2())
            elif command_type == "C_LABEL":
                self.code_writer.writeLabel(self.parser.arg1())
            elif command_type == "C_GOTO":
                self.code_writer.writeGoto(self.parser.arg1())
            elif command_type == "C_IF":
                self.code_writer.writeIf(self.parser.arg1())
            elif command_type == "C_FUNCTION":
                self.code_writer.writeFunction(self.parser.arg1(), self.parser.arg2())
            elif command_type == "C_CALL":
                self.code_writer.writeCall(self.parser.arg1(), self.parser.arg2())
            elif command_type == "C_RETURN":
                self.code_writer.writeReturn()

        self.code_writer.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python VMTranslator.py arquivo.vm")
        sys.exit(1)
    translator = VMTranslator(sys.argv[1])
    translator.translate()
    print("Tradução concluída! Arquivo .asm gerado.")