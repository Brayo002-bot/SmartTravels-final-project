from dataclasses import dataclass
from typing import Dict, List, Optional, Any

VEHICLE_PATTERNS = {
    'bus': [
        {
            'class_key': 'vip_seats',
            'seat_class': 'VIP',
            'segment': 'Front',
            'pattern': ['A', 'B', None, 'C'],
        },
        {
            'class_key': 'normal_seats',
            'seat_class': 'Normal',
            'segment': 'Back',
            'pattern': ['A', 'B', None, 'C', 'D'],
        },
    ],
    'train': [
        {
            'class_key': 'first_class_seats',
            'seat_class': 'First Class',
            'segment': 'Front',
            'pattern': ['A', None, 'B', 'C'],
        },
        {
            'class_key': 'business_seats',
            'seat_class': 'Business',
            'segment': 'Middle',
            'pattern': ['A', 'B', None, 'C', 'D'],
        },
        {
            'class_key': 'economy_seats',
            'seat_class': 'Economy',
            'segment': 'Back',
            'pattern': ['A', 'B', 'C', None, 'D', 'E'],
        },
    ],
    'flight': [
        {
            'class_key': 'first_class_seats',
            'seat_class': 'First Class',
            'segment': 'Front',
            'pattern': ['A', None, 'B', 'C', None, 'D'],
        },
        {
            'class_key': 'business_seats',
            'seat_class': 'Business',
            'segment': 'Middle',
            'pattern': ['A', 'B', None, 'C', 'D', None, 'E', 'F'],
        },
        {
            'class_key': 'economy_seats',
            'seat_class': 'Economy',
            'segment': 'Back',
            'pattern': ['A', 'B', 'C', None, 'D', 'E', 'F', 'G', None, 'H', 'I', 'J'],
        },
    ],
}

CLASS_STYLES = {
    'VIP': 'bg-yellow-500',
    'Normal': 'bg-sky-600',
    'First Class': 'bg-purple-600',
    'Business': 'bg-emerald-600',
    'Economy': 'bg-slate-600',
}

DEFAULT_DISTRIBUTIONS = {
    'bus': {
        'vip_seats': 0.15,
        'normal_seats': 0.85,
    },
    'train': {
        'first_class_seats': 0.10,
        'business_seats': 0.25,
        'economy_seats': 0.65,
    },
    'flight': {
        'first_class_seats': 0.10,
        'business_seats': 0.25,
        'economy_seats': 0.65,
    },
}


def _normalize_distribution(values: Dict[str, float], keys: List[str]) -> Dict[str, float]:
    normalized = {}
    total = sum(max(float(values.get(key, 0) or 0), 0.0) for key in keys)
    if total <= 0:
        return {key: 0.0 for key in keys}

    for key in keys:
        normalized[key] = max(float(values.get(key, 0) or 0), 0.0) / total
    return normalized


def normalize_class_counts(vehicle_type: str, total_passengers: int, distribution: Optional[Dict[str, float]] = None) -> Dict[str, int]:
    vehicle_type = vehicle_type.lower()
    if vehicle_type not in VEHICLE_PATTERNS:
        raise ValueError(f"Unsupported vehicle type: {vehicle_type}")

    keys = [section['class_key'] for section in VEHICLE_PATTERNS[vehicle_type]]
    total_passengers = max(int(total_passengers or 0), 0)
    distribution = distribution or DEFAULT_DISTRIBUTIONS.get(vehicle_type, {})
    normalized = _normalize_distribution(distribution, keys) if distribution else DEFAULT_DISTRIBUTIONS[vehicle_type]

    counts = {}
    remaining = total_passengers

    for key in keys[:-1]:
        counts[key] = int(round(total_passengers * normalized.get(key, 0)))
        remaining -= counts[key]

    counts[keys[-1]] = max(remaining, 0)
    diff = total_passengers - sum(counts.values())
    counts[keys[-1]] += diff

    return {key: max(counts.get(key, 0), 0) for key in keys}


@dataclass
class SeatLayoutResult:
    vehicle_id: Optional[int]
    vehicle_type: str
    layout: List[Dict[str, Any]]
    rows: List[Dict[str, Any]]
    summary: Dict[str, Any]


def _cap_seat_count(value: Optional[int]) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _build_section_rows(section: Dict[str, Any], count: int, start_row: int, booked_numbers: set) -> (List[Dict[str, Any]], List[Dict[str, Any]], int):
    pattern = section['pattern']
    row_capacity = sum(1 for position in pattern if position is not None)
    row = start_row
    layout = []
    rows = []
    remaining = count

    while remaining > 0:
        seats_in_row = min(remaining, row_capacity)
        row_seats = []
        filled = 0
        for position in pattern:
            if position is None:
                row_seats.append({'is_aisle': True})
                continue

            if filled < seats_in_row:
                seat_number = f"{row}{position}"
                is_booked = seat_number in booked_numbers
                seat = {
                    'seat_number': seat_number,
                    'row': row,
                    'column': position,
                    'seat_class': section['seat_class'],
                    'section': section['segment'],
                    'is_booked': is_booked,
                    'booking_status': 'booked' if is_booked else 'available',
                }
                layout.append(seat)
                row_seats.append(seat)
                filled += 1
            else:
                row_seats.append({'is_empty': True})

        rows.append({'row': row, 'segment': section['segment'], 'seat_class': section['seat_class'], 'seats': row_seats})
        remaining -= seats_in_row
        row += 1

    return layout, rows, row


def generate_seat_layout(vehicle_type: str, counts: Dict[str, int], booked_numbers: Optional[List[str]] = None, vehicle_id: Optional[int] = None) -> Dict[str, Any]:
    vehicle_type = vehicle_type.lower()
    if vehicle_type not in VEHICLE_PATTERNS:
        raise ValueError(f"Unsupported vehicle type: {vehicle_type}")

    booked_numbers_set = set(booked_numbers or [])
    layout = []
    rows = []
    current_row = 1
    total_seats = 0
    section_summary = []

    for section in VEHICLE_PATTERNS[vehicle_type]:
        count = _cap_seat_count(counts.get(section['class_key'], 0))
        if count == 0:
            section_summary.append({
                'seat_class': section['seat_class'],
                'count': 0,
                'segment': section['segment'],
            })
            continue

        section_layout, section_rows, current_row = _build_section_rows(section, count, current_row, booked_numbers_set)
        layout.extend(section_layout)
        rows.extend(section_rows)
        total_seats += count
        section_summary.append({
            'seat_class': section['seat_class'],
            'count': count,
            'segment': section['segment'],
        })

    result = SeatLayoutResult(
        vehicle_id=vehicle_id,
        vehicle_type=vehicle_type,
        layout=layout,
        rows=rows,
        summary={
            'total_seats': total_seats,
            'sections': section_summary,
        },
    )

    return {
        'vehicle_id': result.vehicle_id,
        'vehicle_type': result.vehicle_type,
        'layout': result.layout,
        'rows': result.rows,
        'summary': result.summary,
    }


def get_seat_style(seat_class: str) -> str:
    return CLASS_STYLES.get(seat_class, 'bg-gray-500')
