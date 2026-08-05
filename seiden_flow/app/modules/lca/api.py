from __future__ import annotations
from flask import Blueprint, abort, jsonify, render_template, request

def create_lca_blueprint(repo,version,ingress_path_fn,timezone_name):
    bp=Blueprint('lca',__name__)
    @bp.get('/lca')
    @bp.get('/intelligence/lca')
    def portal():return render_template('lca_portal.html',version=version,ingress_path=ingress_path_fn(),display_timezone=timezone_name)
    @bp.get('/api/v1/lca/dashboard')
    def dashboard():return jsonify(repo.dashboard(max(1,min(720,int(request.args.get('hours',24))))))
    @bp.get('/api/v1/lca/devices')
    def devices():return jsonify({'items':repo.devices(request.args.get('include_ignored','false').lower()=='true')})
    @bp.get('/api/v1/lca/devices/ignored')
    def ignored_devices():return jsonify({'items':repo.ignored_devices()})
    @bp.post('/api/v1/lca/devices/<path:device_id>/reactivate')
    def reactivate_device(device_id):
        item=repo.reactivate_device(device_id)
        if not item:abort(404)
        return jsonify(item)
    @bp.delete('/api/v1/lca/devices/<path:device_id>')
    def delete_device(device_id):
        payload=request.get_json(silent=True) or {}
        ok=repo.remove_device(device_id,bool(payload.get('preserve_history',True)),bool(payload.get('ignore_future',False)))
        if not ok:abort(404)
        return jsonify({'removed':True,'device_id':device_id,'preserve_history':bool(payload.get('preserve_history',True)),'ignore_future':bool(payload.get('ignore_future',False))})
    @bp.get('/api/v1/lca/devices/<path:device_id>')
    def device(device_id):
        item=repo.device(device_id)
        if not item:abort(404)
        return jsonify(item)
    @bp.patch('/api/v1/lca/devices/<path:device_id>')
    def update_device(device_id):
        item=repo.update_device(device_id,request.get_json(silent=False) or {})
        if not item:abort(404)
        return jsonify(item)
    @bp.patch('/api/v1/lca/devices/<path:device_id>/channels/<path:channel_key>')
    def update_channel(device_id,channel_key):
        if not repo.device(device_id):abort(404)
        return jsonify(repo.update_channel(device_id,channel_key,request.get_json(silent=False) or {}))
    @bp.get('/api/v1/lca/relationships')
    def relationships():return jsonify(repo.relationship_catalog())
    @bp.get('/api/v1/lca/events')
    def events():return jsonify({'items':repo.events(max(1,min(720,int(request.args.get('hours',24)))),max(1,min(1000,int(request.args.get('limit',200)))),request.args.get('device_id'))})
    return bp
