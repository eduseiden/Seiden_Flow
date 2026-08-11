from __future__ import annotations
from flask import Blueprint, jsonify, render_template, request


def create_ita_blueprint(repo, version, ingress_path_fn, timezone_name):
    bp = Blueprint('ita', __name__)

    @bp.get('/ita')
    @bp.get('/intelligence/ita')
    def portal():
        return render_template('ita_portal.html', version=version, ingress_path=ingress_path_fn(), display_timezone=timezone_name)

    @bp.get('/api/v1/ita/systems')
    def systems():
        return jsonify({'items': repo.systems(request.args.get('view', 'active'))})

    @bp.get('/api/v1/ita/portfolio')
    def portfolio():
        return jsonify(repo.portfolio(request.args.get('view', 'active')))

    @bp.get('/api/v1/ita/systems/<system_id>/current')
    def current(system_id):
        result = repo.current(system_id)
        return (jsonify(result), 200) if result else (jsonify({'error': 'system_not_found'}), 404)

    @bp.get('/api/v1/ita/systems/<system_id>/history')
    def history(system_id):
        return jsonify(repo.history(system_id, request.args.get('hours', 24)))

    @bp.get('/api/v1/ita/systems/<system_id>/events')
    def events(system_id):
        return jsonify(repo.events(system_id, request.args.get('limit', 100)))

    @bp.get('/api/v1/ita/systems/<system_id>/asset-status')
    def asset_status(system_id):
        return jsonify(repo.asset_status(system_id))

    @bp.post('/api/v1/ita/systems/<system_id>/asset-status')
    def set_asset_status(system_id):
        body = request.get_json(silent=True) or {}
        try:
            result = repo.set_asset_status(system_id, body.get('status'), body.get('reason', ''))
        except ValueError:
            return jsonify({'error': 'invalid_asset_status', 'allowed': ['active', 'hidden', 'decommissioned']}), 400
        return jsonify(result)

    return bp
