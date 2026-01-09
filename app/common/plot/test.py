from app.common.plot.extracter import PlotManager


def main():
    manager = PlotManager()

    print("데이터 분석 및 관리를 시작합니다...")
    # plot_input.json을 읽어서 분석 후 plot.json에 자동 반영
    result = manager.process_plot_data("plot_input.json")

    if result:
        # result가 리스트일 경우 첫 번째 항목을 가져오고, 아니면 그대로 사용
        final_data = result[0] if isinstance(result, list) else result

        intent = final_data.get('intent', '의도 파악 불가')
        print(f"분석 완료! 의도: {intent}")
        print("결과가 plot.json에 성공적으로 업데이트되었습니다.")


if __name__ == "__main__":
    main()