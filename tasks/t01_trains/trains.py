def time_to_minutes(time_str):
    parts = time_str.strip().split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    return hours * 60 + minutes, f"{hours:02d}:{minutes:02d}"


def parse_line(line):
    name, rest = line.split(":", 1)
    name = name.strip()

    arr_part, dep_part = rest.split(",", 1)

    arr_str = arr_part.strip().split()[-1]
    dep_str = dep_part.strip().split()[-1]

    arr_min, arr_fmt = time_to_minutes(arr_str)
    dep_min, dep_fmt = time_to_minutes(dep_str)

    if dep_min < arr_min:
        dep_min += 24 * 60

    return arr_min, dep_min, name, arr_fmt, dep_fmt


def main():
    trains = []

    while True:
        try:
            line = input().strip()
        except EOFError:
            break

        if not line or line.startswith("#"):
            continue

        trains.append(parse_line(line))

    if not trains:
        print("Минимальное количество платформ: 0")
        return

    trains.sort(key=lambda item: item[0])

    platform_free_time = []
    platform_trains = []

    for arr_min, dep_min, name, arr_fmt, dep_fmt in trains:
        placed = False

        for i in range(len(platform_free_time)):
            if platform_free_time[i] <= arr_min:
                platform_free_time[i] = dep_min
                platform_trains[i].append(f"{name} ({arr_fmt}–{dep_fmt})")
                placed = True
                break

        if not placed:
            platform_free_time.append(dep_min)
            platform_trains.append([f"{name} ({arr_fmt}–{dep_fmt})"])

    print(f"Минимальное количество платформ: {len(platform_trains)}")
    print()
    print("Распределение по платформам:")
    for i in range(len(platform_trains)):
        trains_list = ", ".join(platform_trains[i])
        print(f"Платформа {i + 1}: {trains_list}")


if __name__ == "__main__":
    main()
