from shape import Shape

def extract_third_quadrant_simplified(shape):
    """Shape의 3번째 사분면만 추출하여 간소화된 형태로 변환"""
    result_layers = []
    
    for layer in shape.layers:
        # 3번째 사분면 (인덱스 2)의 조각 추출
        piece = layer.quadrants[2]
        
        if piece is None:
            result_layers.append('-')
        else:
            # 색상 없는 간소화된 형태로 변환
            shape_char = piece.shape
            if shape_char == 'P':
                result_layers.append('P')
            else:
                result_layers.append(shape_char)
    
    return result_layers

def process_results_file():
    """results.txt를 읽어서 각 줄에 대해 PinPush 연산을 실행하고 결과를 저장"""
    print("results.txt 파일을 읽는 중...")
    
    try:
        with open("derived_combinations_len6.txt", "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        
        print(f"읽어온 줄 수: {len(lines)}")
        
        output_lines = []
        
        for i, line in enumerate(lines):
            try:
                # Shape 객체 생성
                shape = Shape.from_string(line)
                
                # PinPush 연산 실행
                result_shape = shape.push_pin()
                
                # 3번째 사분면만 추출하여 간소화된 형태로 변환
                simplified_layers = extract_third_quadrant_simplified(result_shape)
                
                # 1층부터 나열한 형태로 저장
                output_line = ''.join(simplified_layers)
                output_lines.append(output_line)
                
                print(f"처리 중 ({i+1}/{len(lines)}): {line} -> PinPush -> {output_line}")
                
            except Exception as e:
                print(f"오류 발생 ({i+1}/{len(lines)}): {line} -> {e}")
                output_lines.append("ERROR")
        
        print(f"생성된 결과 수: {len(output_lines)}")
        
        # 결과를 파일로 저장
        output_filename = "pinpush_results.txt"
        with open(output_filename, "w", encoding="utf-8") as f:
            for output_line in output_lines:
                f.write(output_line + "\n")
        
        print(f"결과가 '{output_filename}' 파일에 저장되었습니다.")
        print(f"파일에 저장된 결과 수: {len(output_lines)}")
        
    except FileNotFoundError:
        print("오류: results.txt 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"파일 처리 중 오류 발생: {e}")

if __name__ == "__main__":
    process_results_file() 