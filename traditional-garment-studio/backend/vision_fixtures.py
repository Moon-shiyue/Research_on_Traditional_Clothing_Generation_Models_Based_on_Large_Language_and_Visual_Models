"""Synthetic observation fixtures for tests; never used by recognition."""


def accounted_scene(rows):
    return {'observations':[dict(row,garment_index=i) for i,row in enumerate(rows)],
            'visible_garments':[row.get('component') or 'Unconfirmed garment' for row in rows],
            'single_outfit':True,'all_garments_accounted':True}
